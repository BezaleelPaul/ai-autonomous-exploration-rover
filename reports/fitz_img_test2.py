import fitz
html = '<html><body><h1>Image test</h1><img src="media/image2.png" width="500"><p>After</p></body></html>'
archive = fitz.Archive("reports/pdf_media")
story = fitz.Story(html=html, archive=archive)
writer = fitz.DocumentWriter("reports/fitz_img_test2.pdf")
while True:
    dev = writer.begin_page(fitz.Rect(0, 0, 595, 842))
    more, filled = story.place(fitz.Rect(50, 50, 545, 792))
    story.draw(dev)
    writer.end_page()
    if not more:
        break
writer.close()
print("ok")
