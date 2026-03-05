"""
NEXUS V2 - Batch Processing System
High-volume scanning operations with queue management
"""

import threading
import queue
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class BatchJobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"  
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

@dataclass
class BatchScanJob:
    """Individual scan job in a batch"""
    job_id: str
    card_position: str  # e.g., "A1", "B2", etc.
    scan_regions: List[str] = field(default_factory=lambda: ["title", "set", "number"])
    priority: int = 5  # 1-10, 10 = highest
    status: BatchJobStatus = BatchJobStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3

@dataclass  
class BatchScanResult:
    """Results from a batch scanning operation"""
    batch_id: str
    total_jobs: int
    completed_jobs: int
    successful_jobs: int
    failed_jobs: int
    cancelled_jobs: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    jobs: List[BatchScanJob] = field(default_factory=list)
    
    def get_success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_jobs == 0:
            return 0.0
        return (self.successful_jobs / self.total_jobs) * 100

class BatchScanProcessor:
    """High-performance batch scanning processor"""
    
    def __init__(self, max_workers=3, max_queue_size=1000):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        
        # Queue management
        self.job_queue = queue.PriorityQueue(maxsize=max_queue_size)
        self.result_queue = queue.Queue()
        self.active_jobs = {}
        
        # Worker management
        self.workers = []
        self.running = False
        self.paused = False
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'total_successful': 0,
            'total_failed': 0,
            'average_scan_time': 0.0,
            'current_batch': None
        }
        
        # Callbacks
        self.on_job_complete = None
        self.on_batch_complete = None
        self.on_progress_update = None
        self.on_error = None
        
        # Scanner interface
        self.scanner_interface = None
        
    def set_scanner_interface(self, scanner_interface):
        """Set the scanner interface for batch processing"""
        self.scanner_interface = scanner_interface
        
    def set_callbacks(self,
                     on_job_complete: Optional[Callable] = None,
                     on_batch_complete: Optional[Callable] = None,
                     on_progress_update: Optional[Callable] = None,
                     on_error: Optional[Callable] = None):
        """Set event callbacks"""
        self.on_job_complete = on_job_complete
        self.on_batch_complete = on_batch_complete
        self.on_progress_update = on_progress_update
        self.on_error = on_error
        
    def start(self):
        """Start the batch processing system"""
        if not self.running:
            self.running = True
            self.paused = False
            
            # Start worker threads
            for i in range(self.max_workers):
                worker = threading.Thread(target=self._worker_loop, args=(i,), daemon=True)
                worker.start()
                self.workers.append(worker)
                
            logger.info(f"Batch processor started with {self.max_workers} workers")
    
    def stop(self):
        """Stop the batch processing system"""
        self.running = False
        
        # Clear queue and wait for workers to finish
        while not self.job_queue.empty():
            try:
                self.job_queue.get_nowait()
                self.job_queue.task_done()
            except queue.Empty:
                break
                
        logger.info("Batch processor stopped")
    
    def pause(self):
        """Pause batch processing"""
        self.paused = True
        logger.info("Batch processor paused")
    
    def resume(self):
        """Resume batch processing"""
        self.paused = False
        logger.info("Batch processor resumed")
    
    def submit_batch(self, card_positions: List[str], 
                    batch_id: Optional[str] = None,
                    priority: int = 5,
                    scan_regions: List[str] = None) -> str:
        """Submit a batch of cards for scanning"""
        
        if not batch_id:
            batch_id = f"batch_{int(time.time())}"
            
        if scan_regions is None:
            scan_regions = ["title", "set", "number", "mana", "text"]
        
        # Create jobs for each card position
        jobs = []
        for i, position in enumerate(card_positions):
            job = BatchScanJob(
                job_id=f"{batch_id}_{position}",
                card_position=position,
                scan_regions=scan_regions,
                priority=priority
            )
            jobs.append(job)
            
        # Add jobs to queue
        for job in jobs:
            try:
                # Priority queue uses (priority, item) tuples
                # Lower priority number = higher priority
                queue_item = (10 - job.priority, job)
                self.job_queue.put(queue_item, timeout=1)
                logger.debug(f"Queued job: {job.job_id}")
            except queue.Full:
                logger.error("Job queue is full - cannot add more jobs")
                if self.on_error:
                    self.on_error("Job queue is full")
                break
        
        # Create batch result tracker
        batch_result = BatchScanResult(
            batch_id=batch_id,
            total_jobs=len(jobs),
            completed_jobs=0,
            successful_jobs=0,
            failed_jobs=0,
            cancelled_jobs=0,
            start_time=datetime.now(),
            jobs=jobs
        )
        
        self.stats['current_batch'] = batch_result
        
        logger.info(f"Submitted batch {batch_id} with {len(jobs)} jobs")
        return batch_id
    
    def _worker_loop(self, worker_id: int):
        """Worker thread main loop"""
        logger.info(f"Batch worker {worker_id} started")
        
        while self.running:
            try:
                # Check if paused
                if self.paused:
                    time.sleep(0.1)
                    continue
                
                # Get next job from queue
                try:
                    priority, job = self.job_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # Process the job
                try:
                    self.active_jobs[job.job_id] = job
                    self._process_job(job, worker_id)
                except Exception as e:
                    logger.error(f"Job processing error: {e}")
                    job.status = BatchJobStatus.FAILED
                    job.error = str(e)
                finally:
                    if job.job_id in self.active_jobs:
                        del self.active_jobs[job.job_id]
                    self.job_queue.task_done()
                    
                # Update statistics
                self._update_stats(job)
                
                # Trigger callbacks
                if self.on_job_complete:
                    self.on_job_complete(job)
                    
                # Check if batch is complete
                self._check_batch_completion()
                
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                time.sleep(1)
                
        logger.info(f"Batch worker {worker_id} stopped")
    
    def _process_job(self, job: BatchScanJob, worker_id: int):
        """Process a single scan job"""
        logger.debug(f"Worker {worker_id} processing job: {job.job_id}")
        
        job.status = BatchJobStatus.RUNNING
        job.started_at = datetime.now()
        
        try:
            # Simulate positioning the card (in real implementation, this would
            # communicate with mechanical positioning system)
            self._position_card(job.card_position)
            
            # Perform the scan
            if self.scanner_interface:
                scan_result = self._perform_scan(job)
                
                if scan_result and scan_result.get('success', False):
                    job.result = scan_result
                    job.status = BatchJobStatus.COMPLETED
                    job.completed_at = datetime.now()
                else:
                    raise Exception(f"Scan failed: {scan_result.get('error', 'Unknown error')}")
            else:
                # Simulate scan result for testing
                job.result = self._simulate_scan_result(job)
                job.status = BatchJobStatus.COMPLETED
                job.completed_at = datetime.now()
                
        except Exception as e:
            job.error = str(e)
            
            # Retry logic
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = BatchJobStatus.PENDING
                logger.warning(f"Retrying job {job.job_id} ({job.retry_count}/{job.max_retries})")
                
                # Re-queue the job with lower priority
                retry_priority = max(1, 10 - job.priority + job.retry_count)
                queue_item = (retry_priority, job)
                try:
                    self.job_queue.put(queue_item, timeout=1)
                except queue.Full:
                    job.status = BatchJobStatus.FAILED
                    logger.error(f"Could not re-queue job {job.job_id}")
            else:
                job.status = BatchJobStatus.FAILED
                job.completed_at = datetime.now()
                logger.error(f"Job {job.job_id} failed after {job.max_retries} retries: {e}")
    
    def _position_card(self, position: str):
        """Position the card for scanning (placeholder for mechanical control)"""
        # In a real implementation, this would:
        # 1. Move XY positioning system to the specified position
        # 2. Adjust lighting and camera focus
        # 3. Wait for positioning to complete
        # 4. Verify card is properly positioned
        
        logger.debug(f"Positioning card at {position}")
        time.sleep(0.2)  # Simulate positioning time
    
    def _perform_scan(self, job: BatchScanJob) -> Dict[str, Any]:
        """Perform the actual scan using the scanner interface"""
        try:
            # Configure scan regions
            scan_config = {
                'regions': job.scan_regions,
                'multi_region_validation': True,
                'high_resolution': True,
                'position': job.card_position
            }
            
            # Perform scan
            scan_result = self.scanner_interface.scan_card(scan_config)
            
            return {
                'success': True,
                'data': scan_result,
                'position': job.card_position,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'position': job.card_position,
                'timestamp': datetime.now().isoformat()
            }
    
    def _simulate_scan_result(self, job: BatchScanJob) -> Dict[str, Any]:
        """Simulate scan result for testing purposes"""
        time.sleep(1.5)  # Simulate scan time
        
        return {
            'name': f'Test Card {job.card_position}',
            'set': 'Test Set',
            'collector_number': f'{job.card_position}',
            'confidence': 0.95,
            'position': job.card_position,
            'regions_scanned': len(job.scan_regions),
            'timestamp': datetime.now().isoformat()
        }
    
    def _update_stats(self, job: BatchScanJob):
        """Update processing statistics"""
        self.stats['total_processed'] += 1
        
        if job.status == BatchJobStatus.COMPLETED:
            self.stats['total_successful'] += 1
        elif job.status == BatchJobStatus.FAILED:
            self.stats['total_failed'] += 1
            
        # Update current batch stats
        if self.stats['current_batch']:
            batch = self.stats['current_batch']
            batch.completed_jobs += 1
            
            if job.status == BatchJobStatus.COMPLETED:
                batch.successful_jobs += 1
            elif job.status == BatchJobStatus.FAILED:
                batch.failed_jobs += 1
            elif job.status == BatchJobStatus.CANCELLED:
                batch.cancelled_jobs += 1
    
    def _check_batch_completion(self):
        """Check if current batch is complete and trigger callback"""
        if not self.stats['current_batch']:
            return
            
        batch = self.stats['current_batch']
        
        if batch.completed_jobs >= batch.total_jobs:
            batch.end_time = datetime.now()
            batch.duration = (batch.end_time - batch.start_time).total_seconds()
            
            logger.info(f"Batch {batch.batch_id} completed: {batch.successful_jobs}/{batch.total_jobs} successful")
            
            if self.on_batch_complete:
                self.on_batch_complete(batch)
                
            self.stats['current_batch'] = None
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            'queue_size': self.job_queue.qsize(),
            'max_queue_size': self.max_queue_size,
            'active_jobs': len(self.active_jobs),
            'max_workers': self.max_workers,
            'running': self.running,
            'paused': self.paused,
            'stats': self.stats.copy()
        }
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a specific job"""
        # Check if job is currently active
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            job.status = BatchJobStatus.CANCELLED
            job.completed_at = datetime.now()
            logger.info(f"Cancelled active job: {job_id}")
            return True
        
        # Check queue for pending jobs
        temp_items = []
        cancelled = False
        
        try:
            while True:
                priority, job = self.job_queue.get_nowait()
                if job.job_id == job_id:
                    job.status = BatchJobStatus.CANCELLED
                    job.completed_at = datetime.now()
                    cancelled = True
                    logger.info(f"Cancelled queued job: {job_id}")
                else:
                    temp_items.append((priority, job))
        except queue.Empty:
            pass
        
        # Re-queue non-cancelled jobs
        for item in temp_items:
            self.job_queue.put(item)
            
        return cancelled
    
    def cancel_batch(self, batch_id: str) -> int:
        """Cancel all jobs in a batch"""
        cancelled_count = 0
        
        # Cancel active jobs
        for job_id, job in list(self.active_jobs.items()):
            if job_id.startswith(batch_id):
                job.status = BatchJobStatus.CANCELLED
                job.completed_at = datetime.now()
                cancelled_count += 1
        
        # Cancel queued jobs
        temp_items = []
        try:
            while True:
                priority, job = self.job_queue.get_nowait()
                if job.job_id.startswith(batch_id):
                    job.status = BatchJobStatus.CANCELLED
                    job.completed_at = datetime.now()
                    cancelled_count += 1
                else:
                    temp_items.append((priority, job))
        except queue.Empty:
            pass
        
        # Re-queue non-cancelled jobs
        for item in temp_items:
            self.job_queue.put(item)
            
        logger.info(f"Cancelled {cancelled_count} jobs from batch {batch_id}")
        return cancelled_count
    
    def save_batch_results(self, batch_result: BatchScanResult, filename: Optional[str] = None):
        """Save batch results to file"""
        if not filename:
            timestamp = batch_result.start_time.strftime("%Y%m%d_%H%M%S")
            filename = f"batch_results_{batch_result.batch_id}_{timestamp}.json"
            
        results_dir = Path("data/batch_results")
        results_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = results_dir / filename
        
        # Convert to serializable format
        batch_data = {
            'batch_id': batch_result.batch_id,
            'total_jobs': batch_result.total_jobs,
            'completed_jobs': batch_result.completed_jobs,
            'successful_jobs': batch_result.successful_jobs,
            'failed_jobs': batch_result.failed_jobs,
            'cancelled_jobs': batch_result.cancelled_jobs,
            'success_rate': batch_result.get_success_rate(),
            'start_time': batch_result.start_time.isoformat(),
            'end_time': batch_result.end_time.isoformat() if batch_result.end_time else None,
            'duration': batch_result.duration,
            'jobs': []
        }
        
        # Add job details
        for job in batch_result.jobs:
            job_data = {
                'job_id': job.job_id,
                'card_position': job.card_position,
                'status': job.status.value,
                'result': job.result,
                'error': job.error,
                'created_at': job.created_at.isoformat(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'retry_count': job.retry_count
            }
            batch_data['jobs'].append(job_data)
        
        # Save to file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(batch_data, f, indent=2)
            logger.info(f"Batch results saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save batch results: {e}")

# Global batch processor instance
batch_processor = BatchScanProcessor()

# Convenience functions
def start_batch_processor(max_workers=3, max_queue_size=1000):
    """Start the global batch processor"""
    global batch_processor
    batch_processor = BatchScanProcessor(max_workers, max_queue_size)
    batch_processor.start()
    return batch_processor

def submit_batch_scan(card_positions: List[str], batch_id: Optional[str] = None) -> str:
    """Submit a batch scan job"""
    return batch_processor.submit_batch(card_positions, batch_id)

def get_batch_status() -> Dict[str, Any]:
    """Get current batch processing status"""
    return batch_processor.get_queue_status()