import matplotlib.pyplot as plt
import cv2
from ocr_processor import ContainerOCRProcessor


processor = ContainerOCRProcessor("container_front.pt")

# Process image
image_path = 'Container-side-1/train/Rear/DSCN5808_JPG.rf.6bddde7cec27e18ffcf98f0be6641511.jpg'
result = processor.process_image(image_path, resize_width=640)

if result['success']:
    num_containers = len(result['containers'])
    
    # Create a figure to display crops side-by-side
    fig, axes = plt.subplots(1, num_containers, figsize=(15, 5))
    
    # If only one container, wrap axes in a list to keep it iterable
    if num_containers == 1:
        axes = [axes]

    for i, cont in enumerate(result['containers']):
        print(f"Container {i}:")
        print(f"  ID: {cont['container_id']}")
        print(f"  ISO type: {cont['iso_type']}")

        
        # 1. Convert BGR (OpenCV) to RGB (Matplotlib)
        img_rgb = cv2.cvtColor(cont['cropped'], cv2.COLOR_BGR2RGB)
        
        # 2. Use Matplotlib to display
        axes[i].imshow(img_rgb)
        axes[i].set_title(f"Container {i}: {cont['container_id']}")
        axes[i].axis('off') # Hide the X/Y axes for a cleaner look

    plt.tight_layout()
    plt.show()
else:
    print("No container found.")