"""
Detection Cache - Caching layer for YOLO detections to improve performance
"""
import hashlib
from typing import Dict, List, Optional, Any
from collections import OrderedDict
import numpy as np

from app.utils.logger import get_logger

logger = get_logger(__name__)


class DetectionCache:
    """
    LRU cache for detection results to avoid redundant inference on similar images.
    Uses image hash as key and stores detection results.
    """
    
    def __init__(self, max_size: int = 1000, enabled: bool = True):
        """
        Initialize detection cache.
        
        Args:
            max_size: Maximum number of cached results
            enabled: Whether caching is enabled
        """
        self.max_size = max_size
        self.enabled = enabled
        self.cache: OrderedDict[str, List[Dict[str, Any]]] = OrderedDict()
        self.hits = 0
        self.misses = 0
        
        logger.info(f"DetectionCache initialized (max_size={max_size}, enabled={enabled})")
    
    def _get_image_hash(self, image: np.ndarray) -> str:
        """
        Generate fast hash for image.
        Uses sampling to speed up hashing for large images.
        
        Args:
            image: Input image array
            
        Returns:
            MD5 hash string
        """
        # Sample every 100th byte for speed
        sample = image.tobytes()[::100]
        return hashlib.md5(sample).hexdigest()
    
    def get(self, image: np.ndarray) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached detection results for image.
        
        Args:
            image: Input image array
            
        Returns:
            Cached detections if found, None otherwise
        """
        if not self.enabled:
            return None
        
        img_hash = self._get_image_hash(image)
        
        if img_hash in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(img_hash)
            self.hits += 1
            logger.debug(f"Cache HIT: {img_hash[:8]}... (hits={self.hits}, misses={self.misses})")
            return self.cache[img_hash]
        
        self.misses += 1
        logger.debug(f"Cache MISS: {img_hash[:8]}... (hits={self.hits}, misses={self.misses})")
        return None
    
    def put(self, image: np.ndarray, detections: List[Dict[str, Any]]) -> None:
        """
        Store detection results in cache.
        
        Args:
            image: Input image array
            detections: Detection results to cache
        """
        if not self.enabled:
            return
        
        img_hash = self._get_image_hash(image)
        
        # Add to cache
        self.cache[img_hash] = detections
        self.cache.move_to_end(img_hash)
        
        # Evict oldest if over max size
        if len(self.cache) > self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            logger.debug(f"Cache evicted oldest entry: {oldest_key[:8]}...")
    
    def clear(self) -> None:
        """Clear all cached results."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'enabled': self.enabled,
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'total_requests': total_requests
        }
    
    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"DetectionCache(size={stats['size']}/{stats['max_size']}, "
            f"hit_rate={stats['hit_rate']}, enabled={stats['enabled']})"
        )
