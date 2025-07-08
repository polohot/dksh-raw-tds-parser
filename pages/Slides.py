# import streamlit as st
# import fitz  # PyMuPDF
# from PIL import Image
# from pathlib import Path

# if "images_generated" not in st.session_state:
#     st.session_state.images_generated = True

# # Set layout
# st.set_page_config(layout="wide")

# # Inject custom CSS
# st.markdown("""
#     <style>
#         .main .block-container {
#             max-width: 75%;
#             margin: auto;
#         }
#     </style>
#     """, unsafe_allow_html=True)

# # Paths
# source_pdf = "static/2025-07-07 TDS_PARSE.pdf"
# image_dir = Path("static/images")
# image_dir.mkdir(parents=True, exist_ok=True)

# # Initialize session state
# if "page_index" not in st.session_state:
#     st.session_state.page_index = 1
# if "total_pages" not in st.session_state:
#     st.session_state.total_pages = 0

# # Generate images from PDF only once
# if "images_generated" not in st.session_state:
#     doc = fitz.open(source_pdf)
#     for i, page in enumerate(doc):
#         pix = page.get_pixmap(dpi=800)  # 800 DPI
#         image_path = image_dir / f"page_{i + 1}.png"
#         pix.save(str(image_path))
#     doc.close()

#     st.session_state.total_pages = len(list(image_dir.glob("*.png")))
#     st.session_state.images_generated = True

# # --- FORM BUTTONS ---
# prev_clicked = False
# next_clicked = False

# with st.form("nav_form"):
#     col1, col2, col3 = st.columns([1, 4, 1])

#     with col1:
#         prev_clicked = st.form_submit_button("⬅️ Previous")
#     with col3:
#         next_clicked = st.form_submit_button("Next ➡️")

# # --- UPDATE PAGE INDEX ---
# if prev_clicked and st.session_state.page_index > 1:
#     st.session_state.page_index -= 1

# if next_clicked and st.session_state.page_index < st.session_state.total_pages:
#     st.session_state.page_index += 1

# # --- DISPLAY IMAGE ---
# image_path = image_dir / f"page_{st.session_state.page_index}.png"
# if image_path.exists():
#     image = Image.open(image_path)
#     st.image(image, use_container_width=True)
# else:
#     st.warning("Image not found.")

# st.markdown(
#     f"<div style='text-align: center; font-size: 18px; font-weight: bold;'>"
#     f"Page {st.session_state.page_index} of {st.session_state.total_pages}"
#     f"</div>",
#     unsafe_allow_html=True
# )

# # --- ARROW KEY JS INJECTION ---
# st.markdown(
#     """
#     <script>
#     document.addEventListener("keydown", function(e) {
#         if (e.key === "ArrowRight") {
#             let nextBtn = window.parent.document.querySelector('form button[type="submit"]:nth-child(2)');
#             if (nextBtn) nextBtn.click();
#         }
#         if (e.key === "ArrowLeft") {
#             let prevBtn = window.parent.document.querySelector('form button[type="submit"]:first-child');
#             if (prevBtn) prevBtn.click();
#         }
#     });
#     </script>
#     """,
#     unsafe_allow_html=True
# )
