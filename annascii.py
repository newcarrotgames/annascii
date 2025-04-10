import os
import sys
import re
import requests
import cv2
import numpy as np
from annoy import AnnoyIndex
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO
import tkinter as tk
from tkinter import filedialog, ttk

class ANNASCII:
    def __init__(self, ascii_chars, font_path, font_size=16, glyph_image_size=(32, 32), char_aspect=0.5):
        self.ascii_chars = ascii_chars
        self.font_path = font_path
        self.font_size = font_size
        self.glyph_image_size = glyph_image_size
        self.char_aspect = char_aspect
        self.glyph_dict = {}
        self.index = None
        self.glyph_map = {}

    def clear_glyph_debug_folder(self, folder="glyph_debug"):
        if not os.path.exists(folder):
            return
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

    def get_glyph_size(self, char, font):
        dummy_img = Image.new("L", (100, 100), 0)
        draw = ImageDraw.Draw(dummy_img)
        bbox = draw.textbbox((0, 0), char, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def precompute_glyph_images(self, output_dir="glyph_debug"):
        self.clear_glyph_debug_folder(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        try:
            font = ImageFont.truetype(self.font_path, self.font_size)
        except IOError:
            print("Warning: Could not load TTF font, using default bitmap font")
            font = ImageFont.load_default()

        for ch in self.ascii_chars:
            img = Image.new("L", self.glyph_image_size, color=0)
            draw = ImageDraw.Draw(img)
            left, top, right, bottom = draw.textbbox((0, 0), ch, font=font)
            x = (self.glyph_image_size[0] - (right - left)) // 2
            y = (self.glyph_image_size[1] - (bottom - top)) // 2
            draw.text((x, y), ch, fill=255, font=font)
            self.glyph_dict[ch] = img
            safe_char = re.sub(r'[^a-zA-Z0-9]', lambda m: f"_{ord(m.group(0))}_", ch)
            img.save(os.path.join(output_dir, f"char_{safe_char}.png"))

    def build_annoy_index(self, n_trees=50):
        dim = self.glyph_image_size[0] * self.glyph_image_size[1]
        self.index = AnnoyIndex(dim, metric='euclidean')
        for i, ch in enumerate(self.ascii_chars):
            self.glyph_map[i] = ch
            vec = list(self.glyph_dict[ch].getdata())
            self.index.add_item(i, vec)
        self.index.build(n_trees)

    @staticmethod
    def detect_edges(pil_img, threshold1=100, threshold2=300):
        np_img = np.array(pil_img)
        if len(np_img.shape) == 3:
            np_img = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(np_img, threshold1, threshold2)
        return Image.fromarray(edges, mode='L')

    def convert_image_to_ascii(self, img_path, output_width=100, tile_size=(4, 4)):
        img = Image.open(img_path).convert("L")
        img = self.detect_edges(img)
        aspect_ratio = img.height / img.width
        new_height = int(output_width * aspect_ratio * self.char_aspect)
        img = img.resize((output_width, new_height))

        ascii_lines = []
        for ty in range(0, img.height, tile_size[1]):
            line_chars = []
            for tx in range(0, img.width, tile_size[0]):
                tile = img.crop((tx, ty, tx + tile_size[0], ty + tile_size[1]))
                tile = ImageOps.autocontrast(tile.resize(self.glyph_image_size))
                tile_vec = list(tile.getdata())
                best_glyph_id = self.index.get_nns_by_vector(tile_vec, n=1, search_k=1000)[0]
                line_chars.append(self.glyph_map[best_glyph_id])
            ascii_lines.append("".join(line_chars))

        return "\n".join(ascii_lines)

# UI Implementation using Tkinter with controls for ASCII character set, tile size, glyph size, and font size
class ANNASCIIUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ASCII Art Converter")
        self.setup_ui()

    def setup_ui(self):
        self.frame = ttk.Frame(self.root)
        self.frame.grid(padx=10, pady=10)

        self.img_path = tk.StringVar()
        ttk.Button(self.frame, text="Select Image", command=self.select_image).grid(row=0, column=0, columnspan=2, sticky="ew")

        ttk.Label(self.frame, text="Output Width:").grid(row=1, column=0, sticky="w")
        self.output_width = tk.IntVar(value=150)
        ttk.Entry(self.frame, textvariable=self.output_width).grid(row=1, column=1, sticky="ew")

        ttk.Label(self.frame, text="Tile Size:").grid(row=2, column=0, sticky="w")
        self.tile_size = tk.IntVar(value=4)
        ttk.Entry(self.frame, textvariable=self.tile_size).grid(row=2, column=1, sticky="ew")

        ttk.Label(self.frame, text="Glyph Size:").grid(row=3, column=0, sticky="w")
        self.glyph_size = tk.IntVar(value=32)
        ttk.Entry(self.frame, textvariable=self.glyph_size).grid(row=3, column=1, sticky="ew")

        ttk.Label(self.frame, text="Font Size:").grid(row=4, column=0, sticky="w")
        self.font_size = tk.IntVar(value=16)
        ttk.Entry(self.frame, textvariable=self.font_size).grid(row=4, column=1, sticky="ew")

        ttk.Label(self.frame, text="ASCII Characters:").grid(row=5, column=0, sticky="nw")
        self.ascii_chars = tk.StringVar(value=" .,:;!~+_-<>|\/\"^'-")
        ttk.Entry(self.frame, textvariable=self.ascii_chars, width=50).grid(row=5, column=1, sticky="ew")

        ttk.Button(self.frame, text="Generate ASCII", command=self.generate_ascii).grid(row=6, column=0, columnspan=2, sticky="ew")

        self.text_output = tk.Text(self.frame, width=100, height=40)
        self.text_output.grid(row=7, column=0, columnspan=2, pady=(10, 0))

        # Configure column weights so they expand with the window
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=3)

    def select_image(self):
        self.img_path.set(filedialog.askopenfilename())

    def generate_ascii(self):
        converter = ANNASCII(
            ascii_chars=self.ascii_chars.get(),
            font_path="fonts/Minecraft.ttf",
            font_size=self.font_size.get(),
            glyph_image_size=(self.glyph_size.get(), self.glyph_size.get())
        )
        converter.precompute_glyph_images()
        converter.build_annoy_index()
        ascii_art = converter.convert_image_to_ascii(
            img_path=self.img_path.get(),
            output_width=self.output_width.get(),
            tile_size=(self.tile_size.get(), self.tile_size.get())
        )
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert(tk.END, ascii_art)

if __name__ == "__main__":
    root = tk.Tk()
    app = ANNASCIIUI(root)
    root.mainloop()