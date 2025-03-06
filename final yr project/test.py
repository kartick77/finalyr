import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from ocr_tamil.ocr import OCR
from time import time
import os
from translate import Translator
from PIL import Image, ImageTk
import fitz  # PyMuPDF for PDF handling
import tempfile

os.environ['KMP_DUPLICATE_LIB_OK']='TRUE'

class TamilOCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Tamil OCR Application with Translation")
        self.root.geometry("1200x800")
        
        # Initialize OCR
        self.ocr = OCR(detect=True, details=2, text_threshold=0.3, fp16=False)
        
        # Create GUI elements
        self.create_widgets()
        
        # Store the selected file path
        self.file_path = None
        self.current_image_path = None
        
        # For multi-page documents
        self.pages = []
        self.current_page = 0
        
        # Store the OCR results
        self.ocr_results = None
        self.translated_text = None

    def create_widgets(self):
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create horizontal split
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=5)
        
        # Create vertical split for main content
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left frame for image display
        self.left_frame = ttk.LabelFrame(content_frame, text="Document Preview")
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Right frame for text content
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Select File Button
        self.select_btn = ttk.Button(top_frame, text="Select Document/Image", command=self.select_file)
        self.select_btn.pack(side=tk.LEFT, padx=5)
        
        # Selected file path label
        self.file_label = ttk.Label(top_frame, text="No file selected")
        self.file_label.pack(side=tk.LEFT, padx=5)
        
        # Page navigation for documents (initially hidden)
        self.page_frame = ttk.Frame(top_frame)
        self.page_frame.pack(side=tk.RIGHT, padx=5)
        
        self.prev_page_btn = ttk.Button(self.page_frame, text="Previous", command=self.prev_page)
        self.prev_page_btn.pack(side=tk.LEFT, padx=2)
        
        self.page_label = ttk.Label(self.page_frame, text="Page 1 of 1")
        self.page_label.pack(side=tk.LEFT, padx=5)
        
        self.next_page_btn = ttk.Button(self.page_frame, text="Next", command=self.next_page)
        self.next_page_btn.pack(side=tk.LEFT, padx=2)
        
        self.page_frame.pack_forget()  # Hide until document loaded
        
        # Image/Document display area
        self.canvas = tk.Canvas(self.left_frame, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Process Button
        self.process_btn = ttk.Button(right_frame, text="Process & Translate", command=self.process_file)
        self.process_btn.pack(anchor=tk.W, pady=5)
        
        # Progress label
        self.progress_label = ttk.Label(right_frame, text="")
        self.progress_label.pack(anchor=tk.W, pady=5)
        
        # Create frames for Tamil and English text
        tamil_frame = ttk.LabelFrame(right_frame, text="Tamil Text (Original)")
        tamil_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        english_frame = ttk.LabelFrame(right_frame, text="English Text (Translated)")
        english_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Result Text Areas
        self.tamil_text = scrolledtext.ScrolledText(tamil_frame, width=50, height=12)
        self.tamil_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        self.english_text = scrolledtext.ScrolledText(english_frame, width=50, height=12)
        self.english_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        # Save Buttons Frame
        save_frame = ttk.Frame(right_frame)
        save_frame.pack(pady=5)
        
        # Save Tamil Button
        self.save_tamil_btn = ttk.Button(save_frame, text="Save Tamil Text", 
                                       command=lambda: self.save_results('tamil'))
        self.save_tamil_btn.pack(side=tk.LEFT, padx=5)
        
        # Save English Button
        self.save_english_btn = ttk.Button(save_frame, text="Save English Text", 
                                         command=lambda: self.save_results('english'))
        self.save_english_btn.pack(side=tk.LEFT, padx=5)
        
        # Save Both Button
        self.save_both_btn = ttk.Button(save_frame, text="Save Both", 
                                      command=lambda: self.save_results('both'))
        self.save_both_btn.pack(side=tk.LEFT, padx=5)

    def select_file(self):
        self.file_path = filedialog.askopenfilename(
            filetypes=[
                ("All supported files", "*.pdf *.png *.jpg *.jpeg *.bmp *.gif *.tiff"),
                ("PDF files", "*.pdf"),
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff")
            ]
        )
        if not self.file_path:
            return
            
        self.file_label.config(text=os.path.basename(self.file_path))
        
        # Clear previous results
        self.tamil_text.delete(1.0, tk.END)
        self.english_text.delete(1.0, tk.END)
        self.progress_label.config(text="")
        
        # Clear previous pages
        self.pages = []
        self.current_page = 0
        
        # Handle different file types
        file_ext = os.path.splitext(self.file_path)[1].lower()
        
        if file_ext == '.pdf':
            self.load_pdf()
        else:  # Image file
            self.pages = [self.file_path]
            self.current_image_path = self.file_path
            self.display_image(self.file_path)
            self.page_frame.pack_forget()  # Hide page navigation for single images
            
        # Update page navigation if needed
        self.update_page_navigation()

    def load_pdf(self):
        try:
            self.progress_label.config(text="Loading PDF document...")
            self.root.update()
            
            pdf_document = fitz.open(self.file_path)
            self.pages = []
            
            # Create a temporary directory to store page images
            temp_dir = tempfile.mkdtemp()
            
            # Extract each page as an image
            for page_num in range(pdf_document.page_count):
                page = pdf_document.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))  # Render at 300 DPI
                image_path = os.path.join(temp_dir, f"page_{page_num+1}.png")
                pix.save(image_path)
                self.pages.append(image_path)
            
            if self.pages:
                self.current_page = 0
                self.current_image_path = self.pages[0]
                self.display_image(self.current_image_path)
                
                # Show page navigation if multiple pages
                if len(self.pages) > 1:
                    self.page_frame.pack(side=tk.RIGHT, padx=5)
                else:
                    self.page_frame.pack_forget()
                    
            self.progress_label.config(text=f"PDF loaded with {len(self.pages)} pages")
        except Exception as e:
            messagebox.showerror("Error", f"Error loading PDF: {str(e)}")
            self.progress_label.config(text="Error loading PDF")

    def update_page_navigation(self):
        if len(self.pages) > 1:
            self.page_label.config(text=f"Page {self.current_page + 1} of {len(self.pages)}")
            self.prev_page_btn.config(state=tk.NORMAL if self.current_page > 0 else tk.DISABLED)
            self.next_page_btn.config(state=tk.NORMAL if self.current_page < len(self.pages) - 1 else tk.DISABLED)
            self.page_frame.pack(side=tk.RIGHT, padx=5)
        else:
            self.page_frame.pack_forget()

    def next_page(self):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.current_image_path = self.pages[self.current_page]
            self.display_image(self.current_image_path)
            self.update_page_navigation()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.current_image_path = self.pages[self.current_page]
            self.display_image(self.current_image_path)
            self.update_page_navigation()

    def display_image(self, image_path):
        try:
            # Clear the canvas
            self.canvas.delete("all")
            
            # Open and resize the image to fit the canvas
            image = Image.open(image_path)
            
            # Get canvas dimensions
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width <= 1:  # Canvas not yet realized
                canvas_width = 400
                canvas_height = 600
            
            # Resize image to fit the canvas while preserving aspect ratio
            img_width, img_height = image.size
            ratio = min(canvas_width/img_width, canvas_height/img_height)
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)
            
            image = image.resize((new_width, new_height), Image.LANCZOS)
            
            # Convert to PhotoImage
            self.tk_image = ImageTk.PhotoImage(image)
            
            # Add image to canvas
            self.canvas.create_image(canvas_width//2, canvas_height//2, image=self.tk_image, anchor=tk.CENTER)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error displaying image: {str(e)}")

    def translate_text(self, text):
        try:
            translator = Translator(to_lang="en", from_lang="ta")
            return translator.translate(text)
        except Exception as e:
            return f"Translation error: {str(e)}"

    def process_file(self):
        if not self.current_image_path:
            messagebox.showerror("Error", "Please select a document or image first!")
            return
        
        # Clear previous results
        self.tamil_text.delete(1.0, tk.END)
        self.english_text.delete(1.0, tk.END)
        
        try:
            # Process the image
            start_time = time()
            self.progress_label.config(text="Processing OCR...")
            self.root.update()
            
            self.ocr_results = self.ocr.predict(self.current_image_path)
            
            # Extract Tamil text
            tamil_lines = []
            for item in self.ocr_results:
                current_line = 1
                line_text = ""
                for info in item:
                    text, conf, bbox = info
                    line = bbox[1]
                    if line == current_line:
                        line_text += text + " "
                    else:
                        tamil_lines.append(line_text.strip())
                        line_text = text + " "
                        current_line = line
                tamil_lines.append(line_text.strip())
            
            # Display Tamil text
            tamil_full_text = "\n".join(tamil_lines)
            self.tamil_text.insert(tk.END, tamil_full_text)
            
            # Translate to English
            self.progress_label.config(text="Translating...")
            self.root.update()
            
            # Translate paragraph by paragraph to handle length limitations
            translated_lines = []
            for line in tamil_lines:
                if line.strip():
                    # Split long lines into smaller chunks if needed
                    if len(line) > 500:  # Translate API typically has character limits
                        chunks = [line[i:i+500] for i in range(0, len(line), 500)]
                        translated_chunk = ""
                        for chunk in chunks:
                            translated_chunk += self.translate_text(chunk) + " "
                        translated_lines.append(translated_chunk)
                    else:
                        translated_lines.append(self.translate_text(line))
                else:
                    translated_lines.append("")
            
            # Display English translation
            english_full_text = "\n".join(translated_lines)
            self.english_text.insert(tk.END, english_full_text)
            self.translated_text = english_full_text
            
            end_time = time()
            if len(self.pages) > 1:
                page_info = f" (Page {self.current_page + 1})"
            else:
                page_info = ""
                
            self.progress_label.config(text=f"Completed in {end_time - start_time:.2f} seconds{page_info}")
            
        except Exception as e:
            self.progress_label.config(text="Error occurred")
            messagebox.showerror("Error", f"Processing error: {str(e)}")

    def save_results(self, save_type='both'):
        if save_type == 'tamil' and not self.tamil_text.get(1.0, tk.END).strip():
            messagebox.showerror("Error", "No Tamil text to save!")
            return
        if save_type == 'english' and not self.english_text.get(1.0, tk.END).strip():
            messagebox.showerror("Error", "No English text to save!")
            return
        if save_type == 'both' and (not self.tamil_text.get(1.0, tk.END).strip() or 
                                   not self.english_text.get(1.0, tk.END).strip()):
            messagebox.showerror("Error", "No complete results to save!")
            return
        
        try:
            if save_type == 'both':
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt")],
                    initialfile="ocr_results_both.txt"
                )
                if file_path:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write("TAMIL TEXT:\n")
                        f.write("-" * 50 + "\n")
                        f.write(self.tamil_text.get(1.0, tk.END))
                        f.write("\nENGLISH TRANSLATION:\n")
                        f.write("-" * 50 + "\n")
                        f.write(self.english_text.get(1.0, tk.END))
            else:
                text_to_save = self.tamil_text.get(1.0, tk.END) if save_type == 'tamil' \
                    else self.english_text.get(1.0, tk.END)
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt")],
                    initialfile=f"ocr_results_{save_type}.txt"
                )
                if file_path:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(text_to_save)
            
            if file_path:
                messagebox.showinfo("Success", "Results saved successfully!")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error saving file: {str(e)}")

    def on_canvas_configure(self, event):
        # If an image is loaded, redisplay it when canvas size changes
        if hasattr(self, 'current_image_path') and self.current_image_path:
            self.display_image(self.current_image_path)

def main():
    root = tk.Tk()
    app = TamilOCRApp(root)
    
    # Configure weight for resizing
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)
    
    # Bind canvas resize event
    app.canvas.bind('<Configure>', app.on_canvas_configure)
    
    root.mainloop()

if __name__ == "__main__":
    main()