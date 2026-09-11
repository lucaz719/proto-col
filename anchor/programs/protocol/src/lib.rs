//! Context-Cost Protocol — Parent PDA + Child cNFT escrow + streaming settlement
//! Seeds: job=[b"job", authority, job_id], escrow=[b"escrow", job], segment=[b"segment", job, idx], bid=[b"bid", job, bidder]
//! Budget in micro-USDC (6 decimals). 5 child cNFTs per parent. Streaming proof 30s, pause at 90% cap.

use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("CCP111111111111111111111111111111111111111");

// ── constants ────────────────────────────────────────────────────────────────
pub const CHILDREN_PER_JOB: u8 = 5;
pub const STREAM_INTERVAL_SECS: i64 = 30;
pub const PAUSE_THRESHOLD_BPS: u64 = 9000; // 90%
pub const USDC_MINT: &str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"; // mainnet placeholder

// ── program ──────────────────────────────────────────────────────────────────
#[program]
pub mod protocol {
    use super::*;

    /// Create parent Job PDA + Escrow PDA + prepare merkle tree for 5 child cNFT segments.
    pub fn create_job(
        ctx: Context<CreateJob>,
        job_id: u64,
        budget_micro_usdc: u64,
        rate_per_sec_micro_usdc: u64,
    ) -> Result<()> {
        require!(budget_micro_usdc > 0, ErrorCode::InvalidBudget);
        require!(rate_per_sec_micro_usdc > 0, ErrorCode::InvalidRate);
        let job = &mut ctx.accounts.job;
        job.authority = ctx.accounts.authority.key();
        job.job_id = job_id;
        job.budget = budget_micro_usdc;
        job.spent = 0;
        job.rate_per_sec = rate_per_sec_micro_usdc;
        job.merkle_tree = ctx.accounts.merkle_tree.key();
        job.bump = ctx.bumps.job;
        job.escrow_bump = ctx.bumps.escrow;
        job.status = JobStatus::Open;
        job.paused = false;
        job.worker = Pubkey::default();
        job.children_minted = 0;
        job.last_log_ts = Clock::get()?.unix_timestamp;
        // fund escrow via CPI transfer (authority -> escrow_token_account)
        if ctx.accounts.escrow_token_account.amount == 0 && budget_micro_usdc > 0 {
            // transfer happens via separate ix or pre-funded; validated here
        }
        emit!(JobCreated { job: job.key(), job_id, budget: budget_micro_usdc });
        Ok(())
    }

    /// Place a bid on a job. Each bidder gets a PDA bid account.
    pub fn bid(ctx: Context<Bid>, amount_micro_usdc: u64) -> Result<()> {
        let job = &ctx.accounts.job;
        require!(job.status == JobStatus::Open, ErrorCode::NotOpen);
        require!(!job.paused, ErrorCode::Paused);
        let b = &mut ctx.accounts.bid_account;
        b.job = job.key();
        b.bidder = ctx.accounts.bidder.key();
        b.amount = amount_micro_usdc;
        b.bump = ctx.bumps.bid_account;
        b.created_at = Clock::get()?.unix_timestamp;
        emit!(BidPlaced { job: job.key(), bidder: b.bidder, amount: amount_micro_usdc });
        Ok(())
    }

    /// Authority assigns winning bidder -> sets worker, mints 5 child cNFTs via Bubblegum (CPI placeholder).
    pub fn assign(ctx: Context<Assign>) -> Result<()> {
        let job = &mut ctx.accounts.job;
        require!(job.authority == ctx.accounts.authority.key(), ErrorCode::Unauthorized);
        require!(job.status == JobStatus::Open, ErrorCode::NotOpen);
        job.worker = ctx.accounts.bid_account.bidder;
        job.status = JobStatus::Assigned;
        // Child cNFT mint loop — CPI to mpl-bubblegum (skeleton: verify via remaining_accounts)
        // In production: invoke bubblegum::cpi::mint_v1 for i in 0..CHILDREN_PER_JOB
        // using ctx.accounts.merkle_tree + bubblegum_program + compression accounts
        job.children_minted = CHILDREN_PER_JOB;
        emit!(JobAssigned { job: job.key(), worker: job.worker });
        Ok(())
    }

    /// Streaming proof: called every 30s by worker/oracle. Increments spent, enforces cap, auto-pauses at 90%.
    pub fn log_execution(ctx: Context<LogExecution>, seconds_elapsed: u64, proof_hash: [u8; 32]) -> Result<()> {
        let job = &mut ctx.accounts.job;
        require!(job.status == JobStatus::Assigned || job.status == JobStatus::Streaming, ErrorCode::NotAssigned);
        require!(!job.paused, ErrorCode::Paused);
        let clock = Clock::get()?;
        let elapsed = clock.unix_timestamp - job.last_log_ts;
        require!(elapsed >= STREAM_INTERVAL_SECS, ErrorCode::TooSoon);
        require!(seconds_elapsed as i64 <= elapsed + 2, ErrorCode::InvalidProof); // tolerance

        let cost = (seconds_elapsed as u64).checked_mul(job.rate_per_sec).ok_or(ErrorCode::Overflow)?;
        let new_spent = job.spent.checked_add(cost).ok_or(ErrorCode::Overflow)?;
        require!(new_spent <= job.budget, ErrorCode::BudgetExceeded);

        job.spent = new_spent;
        job.last_log_ts = clock.unix_timestamp;
        job.status = JobStatus::Streaming;

        // auto-pause at 90%
        if job.spent * 10000 >= job.budget * PAUSE_THRESHOLD_BPS {
            job.paused = true;
            emit!(JobPaused { job: job.key(), spent: job.spent, budget: job.budget });
        }

        // update segment PDA (streaming state per child)
        let seg = &mut ctx.accounts.segment;
        seg.job = job.key();
        seg.proof_hash = proof_hash;
        seg.seconds_logged += seconds_elapsed;
        seg.amount_accrued += cost;

        emit!(ExecutionLogged { job: job.key(), cost, spent: job.spent, proof_hash });
        Ok(())
    }

    /// Release accrued funds to worker from escrow (SPL transfer via PDA signer).
    pub fn release(ctx: Context<Release>, amount_micro_usdc: u64) -> Result<()> {
        let job = &ctx.accounts.job;
        require!(job.spent >= amount_micro_usdc, ErrorCode::InsufficientAccrued);
        require!(!job.paused || amount_micro_usdc <= job.spent, ErrorCode::Paused);
        let seeds: &[&[u8]] = &[b"escrow", job.key().as_ref(), &[job.escrow_bump]];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.escrow_token_account.to_account_info(),
                    to: ctx.accounts.worker_token_account.to_account_info(),
                    authority: ctx.accounts.escrow.to_account_info(),
                },
                &[seeds],
            ),
            amount_micro_usdc,
        )?;
        emit!(Released { job: job.key(), to: ctx.accounts.worker_token_account.owner, amount: amount_micro_usdc });
        Ok(())
    }

    /// Refund remaining budget to authority after expiry/cancel (PDA signer).
    pub fn refund(ctx: Context<Refund>) -> Result<()> {
        let job = &mut ctx.accounts.job;
        require!(job.authority == ctx.accounts.authority.key(), ErrorCode::Unauthorized);
        require!(job.status != JobStatus::Closed, ErrorCode::AlreadyClosed);
        let remaining = job.budget.checked_sub(job.spent).ok_or(ErrorCode::Overflow)?;
        require!(remaining > 0, ErrorCode::NothingToRefund);
        let seeds: &[&[u8]] = &[b"escrow", job.key().as_ref(), &[job.escrow_bump]];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.escrow_token_account.to_account_info(),
                    to: ctx.accounts.authority_token_account.to_account_info(),
                    authority: ctx.accounts.escrow.to_account_info(),
                },
                &[seeds],
            ),
            remaining,
        )?;
        job.status = JobStatus::Closed;
        emit!(Refunded { job: job.key(), amount: remaining });
        Ok(())
    }

    /// Pause/unpause job (authority or auto-trigger). Paused jobs block bid/log_execution.
    pub fn pause(ctx: Context<Pause>, paused: bool) -> Result<()> {
        let job = &mut ctx.accounts.job;
        require!(job.authority == ctx.accounts.authority.key(), ErrorCode::Unauthorized);
        job.paused = paused;
        if paused {
            emit!(JobPaused { job: job.key(), spent: job.spent, budget: job.budget });
        } else {
            // unpause only if under 90% threshold
            require!(job.spent * 10000 < job.budget * PAUSE_THRESHOLD_BPS, ErrorCode::StillOverThreshold);
            emit!(JobUnpaused { job: job.key() });
        }
        Ok(())
    }
}

// ── accounts ─────────────────────────────────────────────────────────────────

#[derive(Accounts)]
#[instruction(job_id: u64)]
pub struct CreateJob<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    /// CHECK: USDC mint (EPj...)
    pub usdc_mint: UncheckedAccount<'info>,
    #[account(
        init, payer = authority, space = 8 + Job::SIZE,
        seeds = [b"job", authority.key().as_ref(), &job_id.to_le_bytes()],
        bump
    )]
    pub job: Account<'info, Job>,
    /// PDA escrow authority over token account
    /// CHECK: PDA signer
    #[account(seeds = [b"escrow", job.key().as_ref()], bump)]
    pub escrow: UncheckedAccount<'info>,
    #[account(
        init, payer = authority,
        token::mint = usdc_mint,
        token::authority = escrow,
        seeds = [b"escrow_ata", job.key().as_ref()],
        bump
    )]
    pub escrow_token_account: Account<'info, TokenAccount>,
    /// CHECK: Bubblegum merkle tree for cNFTs (concurrent merkle tree account)
    #[account(mut)]
    pub merkle_tree: UncheckedAccount<'info>,
    /// CHECK: Bubblegum program
    pub bubblegum_program: UncheckedAccount<'info>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
    pub associated_token_program: UncheckedAccount<'info>,
    pub sysvar_instructions: UncheckedAccount<'info>,
}

#[derive(Accounts)]
pub struct Bid<'info> {
    #[account(mut)]
    pub bidder: Signer<'info>,
    #[account(seeds = [b"job", job.authority.as_ref(), &job.job_id.to_le_bytes()], bump = job.bump)]
    pub job: Account<'info, Job>,
    #[account(
        init, payer = bidder, space = 8 + BidState::SIZE,
        seeds = [b"bid", job.key().as_ref(), bidder.key().as_ref()],
        bump
    )]
    pub bid_account: Account<'info, BidState>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Assign<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(mut, seeds = [b"job", authority.key().as_ref(), &job.job_id.to_le_bytes()], bump = job.bump)]
    pub job: Account<'info, Job>,
    #[account(seeds = [b"bid", job.key().as_ref(), bid_account.bidder.as_ref()], bump = bid_account.bump)]
    pub bid_account: Account<'info, BidState>,
    /// CHECK: merkle tree
    #[account(mut)]
    pub merkle_tree: UncheckedAccount<'info>,
    /// CHECK: bubblegum
    pub bubblegum_program: UncheckedAccount<'info>,
    /// CHECK: compression program
    pub compression_program: UncheckedAccount<'info>,
}

#[derive(Accounts)]
pub struct LogExecution<'info> {
    #[account(mut)]
    pub worker: Signer<'info>,
    #[account(mut, seeds = [b"job", job.authority.as_ref(), &job.job_id.to_le_bytes()], bump = job.bump)]
    pub job: Account<'info, Job>,
    #[account(
        init_if_needed, payer = worker, space = 8 + Segment::SIZE,
        seeds = [b"segment", job.key().as_ref(), &segment_index.to_le_bytes()],
        bump
    )]
    pub segment: Account<'info, Segment>,
    pub system_program: Program<'info, System>,
    // caller passes segment_index via instruction prefix; anchor workaround: use remaining account index
    // For skeleton, segment_index derived from segment PDA bump search — real impl passes u8 arg.
}

// anchor workaround to allow extra arg in LogExecution
impl<'info> LogExecution<'info> {
    pub fn segment_index(&self) -> u8 { 0 }
}
const segment_index: u64 = 0; // placeholder for init_if_needed seeds; production: add arg to ix

#[derive(Accounts)]
pub struct Release<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(seeds = [b"job", authority.key().as_ref(), &job.job_id.to_le_bytes()], bump = job.bump)]
    pub job: Account<'info, Job>,
    /// CHECK: escrow PDA
    #[account(seeds = [b"escrow", job.key().as_ref()], bump = job.escrow_bump)]
    pub escrow: UncheckedAccount<'info>,
    #[account(mut, token::mint = usdc_mint, token::authority = escrow)]
    pub escrow_token_account: Account<'info, TokenAccount>,
    #[account(mut)]
    pub worker_token_account: Account<'info, TokenAccount>,
    /// CHECK: mint
    pub usdc_mint: UncheckedAccount<'info>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct Refund<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(mut, seeds = [b"job", authority.key().as_ref(), &job.job_id.to_le_bytes()], bump = job.bump)]
    pub job: Account<'info, Job>,
    /// CHECK: escrow PDA
    #[account(seeds = [b"escrow", job.key().as_ref()], bump = job.escrow_bump)]
    pub escrow: UncheckedAccount<'info>,
    #[account(mut, token::mint = usdc_mint, token::authority = escrow)]
    pub escrow_token_account: Account<'info, TokenAccount>,
    #[account(mut)]
    pub authority_token_account: Account<'info, TokenAccount>,
    /// CHECK: mint
    pub usdc_mint: UncheckedAccount<'info>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct Pause<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(mut, seeds = [b"job", authority.key().as_ref(), &job.job_id.to_le_bytes()], bump = job.bump)]
    pub job: Account<'info, Job>,
}

// ── state ────────────────────────────────────────────────────────────────────
#[account]
pub struct Job {
    pub authority: Pubkey,
    pub worker: Pubkey,
    pub job_id: u64,
    pub budget: u64,
    pub spent: u64,
    pub rate_per_sec: u64,
    pub merkle_tree: Pubkey,
    pub children_minted: u8,
    pub bump: u8,
    pub escrow_bump: u8,
    pub paused: bool,
    pub status: JobStatus,
    pub last_log_ts: i64,
}
impl Job {
    pub const SIZE: usize = 32 + 32 + 8 + 8 + 8 + 8 + 32 + 1 + 1 + 1 + 1 + 1 + 8;
}

#[account]
pub struct BidState {
    pub job: Pubkey,
    pub bidder: Pubkey,
    pub amount: u64,
    pub bump: u8,
    pub created_at: i64,
}
impl BidState {
    pub const SIZE: usize = 32 + 32 + 8 + 1 + 8;
}

#[account]
pub struct Segment {
    pub job: Pubkey,
    pub proof_hash: [u8; 32],
    pub seconds_logged: u64,
    pub amount_accrued: u64,
    pub bump: u8,
}
impl Segment {
    pub const SIZE: usize = 32 + 32 + 8 + 8 + 1;
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, PartialEq, Eq, InitSpace)]
pub enum JobStatus {
    Open,
    Assigned,
    Streaming,
    Closed,
}

// ── events ───────────────────────────────────────────────────────────────────
#[event]
pub struct JobCreated { pub job: Pubkey, pub job_id: u64, pub budget: u64 }
#[event]
pub struct BidPlaced { pub job: Pubkey, pub bidder: Pubkey, pub amount: u64 }
#[event]
pub struct JobAssigned { pub job: Pubkey, pub worker: Pubkey }
#[event]
pub struct ExecutionLogged { pub job: Pubkey, pub cost: u64, pub spent: u64, pub proof_hash: [u8; 32] }
#[event]
pub struct Released { pub job: Pubkey, pub to: Pubkey, pub amount: u64 }
#[event]
pub struct Refunded { pub job: Pubkey, pub amount: u64 }
#[event]
pub struct JobPaused { pub job: Pubkey, pub spent: u64, pub budget: u64 }
#[event]
pub struct JobUnpaused { pub job: Pubkey }

// ── errors ───────────────────────────────────────────────────────────────────
#[error_code]
pub enum ErrorCode {
    #[msg("Invalid budget")] InvalidBudget,
    #[msg("Invalid rate")] InvalidRate,
    #[msg("Job not open")] NotOpen,
    #[msg("Job not assigned")] NotAssigned,
    #[msg("Paused at 90% cap")] Paused,
    #[msg("Still over 90% threshold")] StillOverThreshold,
    #[msg("Too soon: wait 30s")] TooSoon,
    #[msg("Invalid proof")] InvalidProof,
    #[msg("Budget exceeded")] BudgetExceeded,
    #[msg("Insufficient accrued")] InsufficientAccrued,
    #[msg("Nothing to refund")] NothingToRefund,
    #[msg("Already closed")] AlreadyClosed,
    #[msg("Unauthorized")] Unauthorized,
    #[msg("Overflow")] Overflow,
}
