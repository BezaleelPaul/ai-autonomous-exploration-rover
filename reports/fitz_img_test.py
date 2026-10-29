import fitz
from pathlib import Path
p = Path("reports/pdf_media/media/image2.png").resolve().as_uri()
html = f'<html><body><h1>Image test</h1><img src="{p}" width="500"><p>After</p></body></html>'
story = fitz.Story(html=html)
writer = fitz.DocumentWriter("reports/fitz_img_test.pdf")
while True:
    dev = writer.begin_page(fitz.Rect(0, 0, 595, 842))
    more, filled = story.place(fitz.Rect(50, 50, 545, 792))
    story.draw(dev)
    writer.end_page()
    if not more:
        break
writer.close()
print("ok")
