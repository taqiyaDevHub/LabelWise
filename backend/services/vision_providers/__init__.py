"""One module per vision provider. Each exposes:

    analyze(display_image, ocr_result) -> Optional[VisionAnalysis]

returning None (after logging) on any API failure so the caller falls back
to the keyword classifier. Prompt and schema come from vision_classifier.
"""
