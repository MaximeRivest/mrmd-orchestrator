# Image Rendering Test Suite

Comprehensive tests for the mrmd image rendering system, including position modifiers and captions.

---

## 1. Basic Images (Default Block)

Standard markdown images render as centered blocks:

![Mountain landscape](https://picsum.photos/seed/mountain/600/400)

![Ocean sunset](https://picsum.photos/seed/ocean/500/300)

---

## 2. Images with Captions

Using the title attribute for captions:

![Forest path](https://picsum.photos/seed/forest/600/400 "A serene forest path in autumn")

![City skyline](https://picsum.photos/seed/city/600/350 "Downtown metropolitan area at dusk")

---

## 3. Position Modifiers

### 3.1 Align Right (`>`)

![Align right demo](https://picsum.photos/seed/right1/300/200 "Aligned to the right")>

The image above is aligned to the right side of the editor.

---

### 3.2 Align Left (`<`)

![Align left demo](https://picsum.photos/seed/left1/300/200 "Aligned to the left")<

The image above is aligned to the left side of the editor.

---

### 3.3 Wide / Full-Bleed (`^`)

![Wide panorama](https://picsum.photos/seed/panorama/1200/400 "A breathtaking panoramic view")^

This image breaks out of the content column for maximum impact.

---

### 3.4 Small / Thumbnail (`_`)

![Small thumbnail](https://picsum.photos/seed/thumb1/400/300 "A small thumbnail")_

Small images are great for icons or thumbnails that don't need to dominate the page.

---

## 4. Multiple Aligned Images

### 4.1 Alternating Alignment

![First right](https://picsum.photos/seed/multi1/300/200 "Right aligned")>

![Then left](https://picsum.photos/seed/multi2/300/200 "Left aligned")<

![Back to center](https://picsum.photos/seed/multi3/300/200 "Center (default)")

---

### 4.2 Consecutive Right Alignment

![Right 1](https://picsum.photos/seed/rr1/250/150 "First")>

![Right 2](https://picsum.photos/seed/rr2/250/150 "Second")>

---

## 5. Local Images

Testing local file loading:

![Local SVG test](./test-image.svg "Locally stored SVG file")

---

## 6. Reference-Style Images

Defining images separately:

![Nature reference][nature-ref]

![Architecture reference][arch-ref]>

Reference-style image with right alignment.

[nature-ref]: https://picsum.photos/seed/nature-ref/500/350 "Nature scene (reference style)"
[arch-ref]: https://picsum.photos/seed/arch-ref/300/200 "Modern architecture"

---

## 7. Images in Context

### 7.1 In a Blockquote

> Here's an important quote with an image:
>
> ![Quote illustration](https://picsum.photos/seed/quote/400/250 "Illustrating the point")
>
> The image adds visual context to the quoted material.

### 7.2 In a List

Key concepts with illustrations:

1. **Concept One** - Introduction
   ![List image 1](https://picsum.photos/seed/list1/300/150)_

2. **Concept Two** - Development
   ![List image 2](https://picsum.photos/seed/list2/300/150)_

3. **Concept Three** - Conclusion
   ![List image 3](https://picsum.photos/seed/list3/300/150)_

---

## 8. Edge Cases

### 8.1 No Alt Text

![](https://picsum.photos/seed/noalt/300/200)

### 8.2 Very Long Caption

![Long caption test](https://picsum.photos/seed/longcap/400/250 "This is an extremely long caption that contains a lot of descriptive text about the image, explaining in great detail what the viewer should understand about the visual content being presented")

### 8.3 Special Characters in Alt/Caption

![Image with "quotes" & ampersands](https://picsum.photos/seed/special/300/200 "Caption with 'single quotes' and \"double quotes\"")

### 8.4 Small Wide (Contradiction Test)

What happens with `^` on a naturally small image?

![Small source wide display](https://picsum.photos/seed/smallwide/200/100)^

---

## 9. Broken Images (Error Handling)

These should show error states gracefully:

![Invalid URL](https://invalid-domain-xyz.fake/image.png)

![404 Image](https://picsum.photos/this-does-not-exist-12345.jpg)

---

## 10. Images in Tables (Tufte Style)

Tufte loved small visualizations in tables - sparklines, icons, thumbnails:

### Product Comparison

| Product | Preview | Rating | Status |
|---------|---------|--------|--------|
| Alpine Lake | ![](https://picsum.photos/seed/prod1/80/60) | ⭐⭐⭐⭐⭐ | Active |
| Forest Trail | ![](https://picsum.photos/seed/prod2/80/60) | ⭐⭐⭐⭐ | Active |
| Desert Sunset | ![](https://picsum.photos/seed/prod3/80/60) | ⭐⭐⭐ | Pending |










### Team Directory

| Photo | Name | Role |
|-------|------|------|
| ![Avatar](https://picsum.photos/seed/avatar1/50/50) | Alice Chen | Engineering Lead |
| ![Avatar](https://picsum.photos/seed/avatar2/50/50) | Bob Smith | Product Manager |
| ![Avatar](https://picsum.photos/seed/avatar3/50/50) | Carol Davis | Designer |









### Data with Sparklines

| Metric | Trend | Current | Change |
|--------|-------|---------|--------|
| Revenue | ![](https://picsum.photos/seed/spark1/100/30) | $1.2M | +12% |
| Users | ![](https://picsum.photos/seed/spark2/100/30) | 45.2K | +8% |
| Engagement | ![](https://picsum.photos/seed/spark3/100/30) | 72% | -3% |






### Multiple Images in Cell

| Category | Options |
|----------|---------|
| Colors | ![](https://picsum.photos/seed/c1/40/40) ![](https://picsum.photos/seed/c2/40/40) ![](https://picsum.photos/seed/c3/40/40) |
| Sizes | ![S](https://picsum.photos/seed/s1/30/30) ![M](https://picsum.photos/seed/s2/40/40) ![L](https://picsum.photos/seed/s3/50/50) |





---

## 11. Size Comparison

Same image, different positions:

### Default (centered block)
![Size test](https://picsum.photos/seed/sizetest/400/300)

### Small (`_`)
![Size test](https://picsum.photos/seed/sizetest/400/300)_

### Wide (`^`)
![Size test](https://picsum.photos/seed/sizetest/400/300)^

### Float right (`>`)
![Size test](https://picsum.photos/seed/sizetest/400/300)>

Text wrapping around the float-right version of the same image.

---

## 12. Rapid Sequence

Multiple images in quick succession:

![Seq 1](https://picsum.photos/seed/seq1/200/150)
![Seq 2](https://picsum.photos/seed/seq2/200/150)
![Seq 3](https://picsum.photos/seed/seq3/200/150)
![Seq 4](https://picsum.photos/seed/seq4/200/150)

---

## 13. Mixed Content Layout

![Right-aligned illustration](https://picsum.photos/seed/sidebar/350/250 "Sidebar illustration")>

### Section with Right-Aligned Image

The image above is right-aligned. In a block-based editor, each element flows vertically.

**Key points:**
- Block images take their natural height
- Position modifiers control alignment (left, center, right)
- Content flows naturally below each image

> Block widgets render between lines, avoiding the overlap issues of absolute positioning.

---

## Syntax Reference

### Position Modifiers

| Modifier | Syntax | Effect |
|----------|--------|--------|
| Default | `![alt](url)` | Centered block |
| Right | `![alt](url)>` | Align right |
| Left | `![alt](url)<` | Align left |
| Wide | `![alt](url)^` | Full-bleed |
| Small | `![alt](url)_` | Thumbnail |

### Captions

| Feature | Syntax | Effect |
|---------|--------|--------|
| Caption | `![alt](url "caption")` | Caption below image |
| Combined | `![alt](url "caption")>` | Caption + position |

### Tables

Images work inside table cells:

```markdown
| Preview | Name |
|---------|------|
| ![](image.jpg) | Item |
```

---

*End of test suite*
