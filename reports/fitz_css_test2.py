import fitz
css = """
body { font-family: serif; font-size: 11pt; }
h1 { font-size: 18pt; color: #0B2E59; }
h2 { font-size: 13pt; color: #1F4E79; }
p { text-align: justify; }
table { border-collapse: collapse; width: 100%; }
th { background-color: #0B2E59; color: white; }
td, th { border: 1px solid #999; padding: 4px; }
"""
html = '<html><body><h1 id="a">Chapter A</h1><p>Hello</p><h2>Sub</h2><p>More</p><h1 id="b">Chapter B</h1><p>World</p><table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table></body></html>'
story = fitz.Story(html=html, user_css=css)
writer = fitz.DocumentWriter("reports/fitz_css_test2.pdf")
for i in range(20):
    dev = writer.begin_page(fitz.Rect(0, 0, 595, 842))
    more, filled = story.place(fitz.Rect(50, 50, 545, 792))
    story.draw(dev)
    writer.end_page()
    if not more:
        break
writer.close()
print("pages done")
