from docling.document_converter import DocumentConverter
from pathlib import Path
import json
from datetime import datetime
import fitz  # PyMuPDF


class DocumentAnalyzer:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.converter = DocumentConverter()
        self.result = None
        self.doc = None

    def analyze(self):
        """ Run complete analysis on the PDF document. """
        print(f"Starting analysis for: {self.pdf_path}\n")

        # Convert the PDF file
        self.result = self.converter.convert(self.pdf_path)
        self.doc = self.result.document

        #gather stats
        stats = self._get_statistics()

        # Extract components
        self._save_tables()
        self._save_images()
        self._save_markdown()
        self._create_summary_report(stats)

        print("Analysis complete.")

    def _get_statistics(self):
        """ Gather statistics about the document. """
        if self.doc is None:
            raise ValueError("Document not converted yet. Call analyze() first.")

        # Count headings from text elements
        headings = [t for t in self.doc.texts if 'heading' in t.label.lower() or 'section_header' in t.label.lower()]

        stats = {
            "Document Name": self.doc.name,
            "Total Text Elements": len(self.doc.texts),
            "Total Headings": len(headings),
            "Total Tables": len(self.doc.tables),
            "Total Pictures": len(self.doc.pictures)
        }
        return stats
    
    def _save_tables(self):
        """ Extract and save all tables as CSV. """
        if self.doc is None:
            raise ValueError("Document not converted yet. Call analyze() first.")

        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

        for i, table in enumerate(self.doc.tables):
            df = table.export_to_dataframe()
            csv_path = output_dir / f"{Path(self.pdf_path).stem}_table_{i+1}.csv"
            df.to_csv(csv_path, index=False)
            print(f"Table {i+1} saved to: {csv_path}")

    def _save_markdown(self):
        """ Extract and save markdown output. """
        if self.result is None:
            raise ValueError("Document not converted yet. Call analyze() first.")

        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

        markdown = self.result.document.export_to_markdown()
        markdown_path = output_dir / f"{Path(self.pdf_path).stem}.md"
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        print(f"Markdown saved to: {markdown_path}")
    
    def _create_summary_report(self, stats):
        """ Create and save a summary report as JSON. """
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

        report = {
            "Analysis Date": datetime.now().isoformat(),
            "Document Statistics": stats
        }
        report_path = output_dir / f"{Path(self.pdf_path).stem}_summary.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4)
        print(f"Summary report saved to: {report_path}")

    def _save_images(self):
        """ Extract and save images from PDF. """
        if self.doc is None:
            raise ValueError("Document not converted yet. Call analyze() first.")

        # Create images directory in output folder
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        images_dir = output_dir / f"{Path(self.pdf_path).stem}_images"
        images_dir.mkdir(exist_ok=True)

        saved_count = 0
        print("\nExtracting images...")

        # I have used PyMuPDF to extract images directly from the PDF ,
        # docling's image extraction is not reliable.

        doc = fitz.open(self.pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            images = page.get_images()
            for img_index, img in enumerate(images):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                image_path = images_dir / f"page{page_num+1}_img{img_index+1}.{image_ext}"
                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)
                print(f"Image from page {page_num+1}, index {img_index+1} saved to: {image_path}")
                saved_count += 1

        """ deprecated because docling is not good at extracting images. 
        Save all images from the document. 
        if not self.doc.pictures:
            print("No images found in the document.")
            return
        
        
        for i, picture in enumerate(self.doc.pictures, 1):
            try:
                # Pass the document to get_image()
                image_data = picture.get_image(self.doc)
                
                if image_data:
                    from PIL import Image
                    import io
                    
                    # Convert to PIL Image and save
                    img = Image.open(io.BytesIO(image_data))
                    image_path = images_dir / f"image_{i}.png"
                    img.save(image_path)
                    print(f"Image {i} saved to: {image_path}")
                    saved_count += 1
                else:
                    print(f"Picture {i}: No image data returned")
            except Exception as e:
                print(f"Picture {i}: Could not extract - {e}")
        """
        
        print(f"\n✅ Total images saved: {saved_count}/{len(self.doc.pictures)}")

if __name__ == "__main__":
    pdf_path = "./data/Managerial-economics.pdf"
    analyzer = DocumentAnalyzer(pdf_path)
    analyzer.analyze()
