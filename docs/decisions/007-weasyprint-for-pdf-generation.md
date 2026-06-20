# 007 - Use WeasyPrint for PDF Generation

## Status
Accepted

## Context
We needed to select a solution for generating PDF exports of books from HTML content. Requirements included:
- High-quality PDF output with proper typography and layout
- Support for CSS styling (including @media print, page breaks)
- Ability to handle long documents (books with multiple chapters)
- Support for headers, footers, and page numbering
- Good Unicode and international character support
- Reasonable performance for on-demand generation
- Ability to embed images and styled content
- Open-source licensing suitable for commercial use
- Minimal external dependencies for deployment simplicity

Options evaluated:
- WeasyPrint (HTML/CSS to PDF rendering engine)
- ReportLab (programmatic PDF generation)
- xhtml2pdf (pip install xhtml2pdf)
- wkhtmltopdf (Qt WebKit wrapper)
- Puppeteer/Playwright (headless browser PDF generation)
- LaTeX (document preparation system)
- PDFKit (WKHTMLTOPDF wrapper)
- Manual PDF assembly (low-level PDF manipulation)

## Decision
Selected WeasyPrint for PDF generation because it provides:
- Excellent CSS2.1 and partial CSS3 support for styling
- True HTML-to-PDF layout (not absolute positioning hacks)
- Built-in support for @media print and page-break properties
- Automatic table of contents and index generation capabilities
- Good handling of long documents with flowable elements
- Support for CSS-driven page headers, footers, and margin notes
- Strong Unicode and internationalization support
- Pure Python implementation with minimal native dependencies
- Open-source BSD license (commercially friendly)
- Active maintenance and good documentation
- Ability to generate PDFs from HTML strings or files
- Support for PDF/A-1b compliance (important for archival)
- Less resource-intensive than full browser-based solutions
- Easy installation and deployment in containerized environments

## Consequences
### Positive
- High-fidelity PDF output that respects web design principles
- Consistent styling between HTML preview and PDF output
- Declarative styling approach (CSS) vs. imperative drawing commands
- Good balance of features and performance
- Reduced dependency complexity compared to browser-based solutions
- No need for separate JavaScript/V8 runtime (unlike Puppeteer)
- Output suitable for both digital distribution and print
- Active community and responsive maintainers
- Easy to customize PDF appearance through CSS modifications

### Negative
- Less JavaScript support than full browser engines (but CSS often sufficient)
- Some advanced CSS3 features may be missing or partial
- Not as fast as extremely simplified PDF generators
- Limited to what can be expressed in HTML/CSS (no direct PDF primitives)
- May require tweaking complex layouts for optimal PDF output
- Fewer visual debugging tools compared to browser devtools

### Neutral
- Leverages existing HTML/CSS skills already used for web exports
- Complements our HTML and Markdown export options nicely
- Part of a graduated quality spectrum: Markdown < HTML < PDF
- Can be replaced with alternative solutions if performance becomes critical
- Uses common web technologies reducing context switching for developers

## Related Documents
- [API.md](../API.md) - PDF export endpoint (`GET /books/{id}/export/pdf`)
- Source code in `app/services/export_service.py` (PDF generation logic)
- Source code in `app/models.py` (export-related response models)
- Template HTML/CSS in export_service.py showing styling approach
- Configuration documentation for export service settings
- Example PDF outputs demonstrating quality and formatting