import fitz  # PyMuPDF
import io
from PIL import Image
import os

def extract_images_from_pdf(pdf_path, output_dir="extracted_images"):
    """
    Extracts all images from a PDF and saves them to a directory.

    :param pdf_path: Path to the PDF file.
    :param output_dir: Directory to save the extracted images.
    """
    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Open the PDF file
    pdf_file = fitz.open(pdf_path)

    # Iterate through each page of the PDF
    for page_index in range(len(pdf_file)):
        page = pdf_file[page_index]
        image_list = page.get_images(full=True)

        # Print the number of images found on the page
        if image_list:
            print(f"[+] Found {len(image_list)} images on page {page_index + 1}")
        else:
            print(f"[!] No images found on page {page_index + 1}")

        # Loop through all the images on the page
        for image_index, img in enumerate(image_list, start=1):
            # Get the XREF of the image
            xref = img[0]

            # Extract the image bytes
            base_image = pdf_file.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            # Create a PIL Image object
            try:
                image = Image.open(io.BytesIO(image_bytes))
                
                # Define the image filename
                image_filename = f"page{page_index + 1}_img{image_index}.{image_ext}"
                output_path = os.path.join(output_dir, image_filename)

                # Save the image
                image.save(open(output_path, "wb"))
                print(f"    - Saved image: {output_path}")

            except Exception as e:
                print(f"    - Error processing image: {e}")

    pdf_file.close()

# --- Example Usage ---
if __name__ == "__main__":
    pdf_file_path = "Interim&final_report/IS313 Final_report.pdf"  # Replace with your PDF file path
    extract_images_from_pdf(pdf_file_path, "docs/assets")
