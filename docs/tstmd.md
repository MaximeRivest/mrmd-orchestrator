# Markdown Image Rendering Test Suite

This document contains various image markdown patterns to test your renderer's image handling capabilities.

---

## 1. Basic Inline Images

Standard markdown image syntax:

![Alt text for a sample image](https://picsum.photos/400/200)

![Mountain landscape](https://picsum.photos/seed/mountain/600/300)

---

## 2. Images with Titles

Images with hover title text:

![A cityscape at night](https://picsum.photos/seed/city/500/250 "City skyline at sunset")

![Abstract art](https://picsum.photos/seed/abstract/400/400 "Colorful abstract pattern")

---

## 3. Reference-Style Images

Defining images separately from their usage:

![Nature scene][nature]
![Ocean waves][ocean]
![Forest path][forest]

[nature]: https://picsum.photos/seed/nature/500/300 "Beautiful nature"
[ocean]: https://picsum.photos/seed/ocean/500/300 "Ocean view"
[forest]: https://picsum.photos/seed/forest/500/300

---

## 4. Images with Empty or Missing Alt Text

Testing accessibility edge cases:

![](https://picsum.photos/seed/empty/300/200)

![ ](https://picsum.photos/seed/space/300/200)

---

## 5. Broken/Invalid Image URLs

Testing error handling for missing images:

![This image should fail](https://invalid-domain-that-does-not-exist.fake/image.png)

![Another broken image](https://example.com/nonexistent-image-12345.jpg)

![Malformed URL](not-a-valid-url)

---

## 6. Images in Different Contexts

### Inside a Paragraph

Here is some text with an inline image ![small icon](https://picsum.photos/seed/icon/50/50) embedded right in the middle of the paragraph, and the text continues after it.

### Inside a Blockquote

> This is a blockquote containing an image:
> 
> ![Quoted image](https://picsum.photos/seed/quote/400/200)
> 
> The image appears within the quote.

### Inside a List

- First item with image: ![List image 1](https://picsum.photos/seed/list1/150/100)
- Second item with image: ![List image 2](https://picsum.photos/seed/list2/150/100)
- Third item without image

1. Numbered item one ![Numbered image](https://picsum.photos/seed/num1/150/100)
2. Numbered item two
3. Numbered item three with image ![Another numbered](https://picsum.photos/seed/num3/150/100)

### Inside a Table

| Image 1 | Image 2 | Description |
|---------|---------|-------------|
| ![Table img A](https://picsum.photos/seed/tableA/100/100) | ![Table img B](https://picsum.photos/seed/tableB/100/100) | Two images |
| ![Table img C](https://picsum.photos/seed/tableC/100/100) | Text only | Mixed content |

---

## 7. Various Image Sizes

Testing different dimensions:

![Tiny](https://picsum.photos/50/50)

![Small square](https://picsum.photos/100/100)

![Wide banner](https://picsum.photos/800/100)

![Tall vertical](https://picsum.photos/150/400)

![Large](https://picsum.photos/800/600)

---

## 8. HTML Image Tags (if supported)

Some renderers support inline HTML:

<img src="https://picsum.photos/seed/html1/300/200" alt="HTML image tag">

<img src="https://picsum.photos/seed/html2/400/250" alt="With dimensions" width="400" height="250">

<img src="https://picsum.photos/seed/html3/300/200" alt="Styled image" style="border: 2px solid red; border-radius: 10px;">

---

## 9. Images as Links

Clickable images:

[![Clickable image](https://picsum.photos/seed/click/300/200)](https://example.com)

[![Link with title](https://picsum.photos/seed/link/300/200 "Click me!")](https://example.com "Go to example.com")

---

## 10. Special Characters in Alt Text and URLs

![Image with "quotes" and 'apostrophes'](https://picsum.photos/seed/special1/300/200)

![Spëcîal çhàrâctérs](https://picsum.photos/seed/special2/300/200)

![Alt with <angle> & ampersand](https://picsum.photos/seed/special3/300/200)

---

## 11. Data URI Images (Base64)

Small inline base64 encoded image:

![Red dot](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA AAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO 9TXL0Y4OHwAAAABJRU5ErkJggg==)

---

## 12. Multiple Images in Sequence

Testing layout of consecutive images:

![Sequence 1](https://picsum.photos/seed/seq1/200/150)
![Sequence 2](https://picsum.photos/seed/seq2/200/150)
![Sequence 3](https://picsum.photos/seed/seq3/200/150)

---

## 13. Images with Query Parameters

URLs containing query strings:

![With query params](https://picsum.photos/300/200?grayscale)

![Multiple params](https://picsum.photos/300/200?grayscale&blur=2)

---

## 14. Edge Cases

### Very Long Alt Text

![This is an extremely long alt text that goes on and on and contains a lot of descriptive information about what the image supposedly contains, which might cause layout issues in some renderers if not handled properly](https://picsum.photos/seed/longalt/300/200)

### Empty Image Source

![Alt text but no src]()

### Whitespace Variations

![  Padded alt  ](https://picsum.photos/seed/padded/300/200)

![Trailing space ](https://picsum.photos/seed/trailing/300/200 )

---

## Test Complete

If all sections above render correctly (or fail gracefully where expected), your image handling is working well!