import logging
from .camera_pipeline import CameraPipeline

def run_camera_pipeline(process_args: dict):
    import signal
    import sys
    import os
    from typing import Optional, Dict
    
    # Setup logging for the process
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(f"CameraProcess-{process_args['cam_id']}")
    
    # Extract arguments - REMOVED TRAILING COMMAS
    cam_id = process_args['cam_id']
    config = process_args['config']
    gpu_available = process_args['gpu_available']
    display_width = process_args['display_width']
    display_height = process_args['display_height']
    ai_in_q = process_args['ai_in_q']     # Fix: removed comma
    ai_out_q = process_args['ai_out_q']   # Fix: removed comma
    shutdown_pipe = process_args['shutdown_pipe']
    performance_stats = process_args.get('performance_stats', None)
    
    pipeline = None
    try:
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down")
            if pipeline:
                pipeline.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        if shutdown_pipe:
            shutdown_pipe.send({
                'status': 'initialized',
                'pid': os.getpid(),
                'cam_id': cam_id
            })

        # Create pipeline with correct queue objects
        pipeline = CameraPipeline(
            cam_id=cam_id,
            config=config,
            gpu_available=gpu_available,
            display_width=display_width,
            display_height=display_height,
            ai_in_q=ai_in_q,
            ai_out_q=ai_out_q,
            shutdown_pipe=shutdown_pipe,
            performance_stats=performance_stats
        )
        
        success = pipeline.start()
        
        if not success:
            logger.error(f"Pipeline failed to start")
            if shutdown_pipe:
                shutdown_pipe.send({
                    'status': 'failed',
                    'error': 'Pipeline start failed'
                })
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error in process {cam_id}: {e}")
        import traceback
        traceback.print_exc()
        if shutdown_pipe:
            try:
                shutdown_pipe.send({
                    'status': 'failed',
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
            except:
                pass
        sys.exit(1)
    
    finally:
        if pipeline:
            pipeline.stop()
        if shutdown_pipe:
            try:
                shutdown_pipe.close()
            except:
                pass
