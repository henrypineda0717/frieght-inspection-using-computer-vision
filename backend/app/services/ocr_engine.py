
import os

# Force disable oneDNN at the system level before importing Paddle
os.environ['FLAGS_use_onednn'] = '0' 

from paddleocr import PaddleOCR

class OCREngine:
    def __init__(self):
        self.ocr = PaddleOCR(
            text_detection_model_name='PP-OCRv5_mobile_det',
            text_recognition_model_name='PP-OCRv5_mobile_rec',
            use_doc_unwarping=False,              
            use_doc_orientation_classify=False,   
            use_textline_orientation=False,       
            # CHANGE: Set this to False to avoid the NotImplementedError
            enable_mkldnn=False,                   
            cpu_threads=1,                        
            text_det_limit_type='max',
            text_det_limit_side_len=960           
        )
    def predict(self, frame):
        return self.ocr.predict(frame)