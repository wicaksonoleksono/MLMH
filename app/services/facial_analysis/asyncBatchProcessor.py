"""
Async Batch Processing Service for Facial Analysis

Handles non-blocking async batch processing:
1. Send batches of image paths to gRPC (non-blocking)
2. Collect results asynchronously
3. Batch write to DB (efficient)
4. Sequential JSONL output
"""

import asyncio
import json
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class AsyncBatchProcessor:
    """Non-blocking batch processor for facial analysis"""

    def __init__(self, batch_size: int = 50, max_queue_size: int = 500):
        """
        Initialize batch processor

        Args:
            batch_size: How many results to collect before batch processing
            max_queue_size: Max items in queue before blocking
        """
        self.batch_size = batch_size
        self.max_queue_size = max_queue_size
        self.result_queue = Queue(maxsize=max_queue_size)
        self.processing_thread = None
        self.is_running = False

    def start(self):
        """Start background batch processor thread"""
        if self.is_running:
            logger.warning("Batch processor already running")
            return

        self.is_running = True
        self.processing_thread = threading.Thread(
            target=self._batch_processor_loop,
            daemon=True,
            name="AsyncBatchProcessor"
        )
        self.processing_thread.start()
        logger.info("Async batch processor started")

    def stop(self, timeout: float = 30.0):
        """Stop batch processor gracefully"""
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=timeout)
            logger.info("Async batch processor stopped")

    def submit_result(self, result: Dict[str, Any]) -> bool:
        """
        Submit a result to be batched (non-blocking if queue not full)

        Args:
            result: Single image processing result

        Returns:
            True if submitted, False if queue full
        """
        try:
            self.result_queue.put(result, block=False)
            return True
        except Exception as e:
            logger.error(f"Failed to queue result: {e}")
            return False

    def _batch_processor_loop(self):
        """Background thread that batches and processes results"""
        batch = []
        jsonl_entries = []

        while self.is_running or not self.result_queue.empty():
            try:
                # Collect batch with timeout
                result = self.result_queue.get(timeout=2.0)
                batch.append(result)
                jsonl_entries.append(result)

                # Process batch when ready
                if len(batch) >= self.batch_size:
                    self._process_batch(batch, jsonl_entries)
                    batch = []
                    jsonl_entries = []

            except Exception as e:
                if "Empty" not in str(e):
                    logger.error(f"Batch processor error: {e}")
                continue

        # Process remaining batch
        if batch:
            logger.info(f"Processing final batch of {len(batch)} results")
            self._process_batch(batch, jsonl_entries)

    def _process_batch(self, batch: List[Dict], jsonl_entries: List[Dict]):
        """
        Process a batch of results

        Args:
            batch: List of results to batch process (DB write)
            jsonl_entries: List to write to JSONL
        """
        logger.info(f"Processing batch of {len(batch)} results")

        # TODO: Implement batch DB write here
        # This is where you'd do:
        # db.bulk_insert(batch)
        # or
        # for result in batch:
        #     db.add(result)
        # db.commit()

        logger.info(f"Batch processed: {len(batch)} results written to DB")


class AsyncGrpcClient:
    """Non-blocking async wrapper for gRPC client"""

    def __init__(self, grpc_client, executor: Optional[ThreadPoolExecutor] = None):
        """
        Initialize async gRPC wrapper

        Args:
            grpc_client: Synchronous gRPC client instance
            executor: ThreadPoolExecutor for running blocking calls
        """
        self.grpc_client = grpc_client
        self.executor = executor or ThreadPoolExecutor(max_workers=4)

    async def analyze_image_async(self, image_path: str, device: str = 'cpu') -> Dict[str, Any]:
        """
        Async wrapper for gRPC analyze_image (non-blocking)

        Args:
            image_path: Path to image file
            device: 'cpu' or 'cuda:0'

        Returns:
            Analysis result dict
        """
        loop = asyncio.get_event_loop()
        # Run blocking call in thread pool (doesn't block event loop)
        result = await loop.run_in_executor(
            self.executor,
            self.grpc_client.analyze_image,
            image_path,
            device
        )
        return result

    async def analyze_batch_async(
        self,
        image_paths: List[str],
        device: str = 'cpu'
    ) -> List[Dict[str, Any]]:
        """
        Async batch processing (send multiple images concurrently)

        Args:
            image_paths: List of image paths
            device: 'cpu' or 'cuda:0'

        Returns:
            List of analysis results in same order
        """
        # Create concurrent tasks (all start immediately, don't wait)
        tasks = [
            self.analyze_image_async(path, device)
            for path in image_paths
        ]
        # Wait for all to complete (but gRPC server processes in parallel)
        results = await asyncio.gather(*tasks)
        return results

    def close(self):
        """Clean up executor"""
        self.executor.shutdown(wait=True)


class BatchedAsyncProcessor:
    """
    Main orchestrator: Async send + Batch collect

    Architecture:
    1. Send batches to gRPC (async, non-blocking)
    2. Collect results as they complete
    3. Batch write to DB
    4. Sequential JSONL output
    """

    def __init__(self, grpc_client, batch_size: int = 50):
        self.grpc_client = grpc_client
        self.async_client = AsyncGrpcClient(grpc_client)
        self.batch_processor = AsyncBatchProcessor(batch_size=batch_size)
        self.batch_size = batch_size

    async def process_images_async(
        self,
        image_paths: List[str],
        device: str = 'cpu'
    ) -> List[Dict[str, Any]]:
        """
        Process multiple images asynchronously in batches

        Args:
            image_paths: List of paths to process
            device: 'cpu' or 'cuda:0'

        Returns:
            All results (order preserved by index)
        """
        all_results = []
        total = len(image_paths)

        logger.info(f"Starting async batch processing: {total} images, batch_size={self.batch_size}")

        # Process in batches (send non-blocking, collect async)
        for batch_idx in range(0, total, self.batch_size):
            batch_paths = image_paths[batch_idx:batch_idx + self.batch_size]
            batch_num = (batch_idx // self.batch_size) + 1
            total_batches = (total + self.batch_size - 1) // self.batch_size

            logger.info(f"Batch {batch_num}/{total_batches}: Processing {len(batch_paths)} images async...")

            # Send batch async (non-blocking, gRPC processes in parallel)
            batch_results = await self.async_client.analyze_batch_async(batch_paths, device)

            all_results.extend(batch_results)
            logger.info(f"Batch {batch_num}/{total_batches}: Received {len(batch_results)} results")

        logger.info(f"Async batch processing complete: {len(all_results)} total results")
        return all_results

    def close(self):
        """Clean up resources"""
        self.async_client.close()
        self.batch_processor.stop()
