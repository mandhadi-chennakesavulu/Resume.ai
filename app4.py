import streamlit as st
import google.generativeai as genai
import os
import PyPDF2 as pdf
from docx import Document
from dotenv import load_dotenv
import sqlite3
from datetime import datetime
import time
from io import BytesIO
import base64
from zipfile import ZipFile
import pandas as pd

# Load environment variables
load_dotenv()

# Configure Generative AI API key from environment variables
api_key = "AIzaSyB_MfpqTjenjmCAqczJ0eoRvKiyMXxRVFM"
if api_key is None:
    st.error("API key not found. Please set the GENAI_API_KEY environment variable.")
    st.stop()

genai.configure(api_key=api_key)

# Database connection
conn = sqlite3.connect('resumes.db')
c = conn.cursor()

# Create table if it does not exist
c.execute('''CREATE TABLE IF NOT EXISTS resumes
             (id INTEGER PRIMARY KEY, name TEXT, text TEXT, file BLOB, upload_date TIMESTAMP)''')
conn.commit()

# Define the prompt template
input_prompt = """
Hey, act like a skilled or very experienced ATS (Application Tracking System)
with a deep understanding of the tech field, software engineering, data science, data analysis,
and data engineering. Your task is to evaluate the resume based on the given job description.
Consider the job market is very competitive and provide the best assistance for improving the resumes.
Assign the percentage matching based on JD (Job Description) and the missing keywords with high accuracy.

Give the results as:
JD Match: <percentage>
Missing Keywords: [list]
Profile Summary: <summary>
"""

# Function to instantiate model and get response
def get_gemini_response(input):
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(input)
    return response.text

# Function to extract text from PDF
def input_pdf_text(uploaded_file):
    reader = pdf.PdfReader(uploaded_file)
    text = ""
    for page_n in range(len(reader.pages)):
        page = reader.pages[page_n]
        text += str(page.extract_text())
    return text

# Function to extract text from DOCX
def input_docx_text(uploaded_file):
    doc = Document(uploaded_file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

# Function to insert resume into database
def insert_resume(name, text, file_bytes):
    c.execute('INSERT INTO resumes (name, text, file, upload_date) VALUES (?, ?, ?, ?)', 
              (name, text, file_bytes, datetime.now()))
    conn.commit()

# Function to fetch resumes from database
def fetch_resumes():
    c.execute('SELECT DISTINCT name, upload_date FROM resumes')
    return c.fetchall()

# Function to match resumes to a job description
def match_resumes(jd_text):
    results = []
    resumes = fetch_resumes()
    for resume in resumes:
        filename = resume[0]
        c.execute('SELECT text FROM resumes WHERE name=? ORDER BY upload_date DESC LIMIT 1', (filename,))
        resume_text = c.fetchone()[0]
        
        # Generate AI response
        full_prompt = input_prompt + f"\nJob Description:\n{jd_text}\nResume:\n{resume_text}"
        response_text = get_gemini_response(full_prompt)

        # Handle parsing and create results
        try:
            match_index = response_text.find("JD Match:")
            if match_index != -1:
                match_line = response_text[match_index:].splitlines()[0]
                match_percentage_str = match_line.split(":")[1].strip().replace("%", "")
                match_percentage = float(''.join(filter(str.isdigit, match_percentage_str)) or 0)  # Extract digits
            else:
                match_percentage = 0

            # Determine suitability
            suitability = "Suitable" if match_percentage >= 60 else "Not Suitable"

            # Create a link for the resume file
            c.execute('SELECT file FROM resumes WHERE name=? ORDER BY upload_date DESC LIMIT 1', (filename,))
            file_bytes = c.fetchone()[0]
            encoded_bytes = base64.b64encode(file_bytes).decode('utf-8')
            resume_link = f'<a href="data:application/octet-stream;base64,{encoded_bytes}" download="{filename}">Download</a>'

            results.append({
                "name": filename,
                "suitability": suitability,
                "link": resume_link
            })

        except Exception as e:
            st.error(f"Error processing resume '{filename}': {str(e)}")
            continue

    return results

# Function to create a download link for multiple files as a zip
def create_zip_download(files, zip_name):
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as zip_file:
        for file_name, file_bytes in files:
            zip_file.writestr(file_name, file_bytes)
    zip_buffer.seek(0)  # Move to the start of the BytesIO buffer
    return zip_buffer

# Function to delete resume from database
def delete_resume(filename):
    c.execute('DELETE FROM resumes WHERE name=?', (filename,))
    conn.commit()

# Function to remove duplicate resumes from database
def remove_duplicates():
    c.execute('DELETE FROM resumes WHERE id NOT IN (SELECT MIN(id) FROM resumes GROUP BY name)')
    conn.commit()

# Function to delete entire database
def delete_database():
    c.execute('DROP TABLE IF EXISTS resumes')
    conn.commit()

# Streamlit app
st.title("Resume Screening Software (ATS)")
st.subheader("Upload and Analyze Resumes Against Job Descriptions")

# Job Description Input
jd = st.text_area("Paste the Job Description")

# Resume Upload
uploaded_files = st.file_uploader("Upload Resumes", type=["pdf", "docx"], accept_multiple_files=True, help="Please upload PDF or DOCX files.")

# Submit button for immediate analysis
if st.button("Submit") and uploaded_files:
    suitable_files = []
    unsuitable_files = []
    results = []

    for uploaded_file in uploaded_files:
        try:
            # Extract text based on file type
            if uploaded_file.type == "application/pdf":
                text = input_pdf_text(uploaded_file)
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                text = input_docx_text(uploaded_file)

            # Generate AI response
            full_prompt = input_prompt + f"\nJob Description:\n{jd}\nResume:\n{text}"
            response_text = get_gemini_response(full_prompt)

            # Handle parsing and create results
            match_index = response_text.find("JD Match:")
            if match_index != -1:
                match_line = response_text[match_index:].splitlines()[0]
                match_percentage_str = match_line.split(":")[1].strip().replace("%", "")
                match_percentage = float(''.join(filter(str.isdigit, match_percentage_str)) or 0)  # Extract digits
            else:
                match_percentage = 0

            # Determine suitability
            suitability = "Suitable" if match_percentage >= 60 else "Not Suitable"

            # Store results and files for download
            if suitability == "Suitable":
                suitable_files.append((uploaded_file.name, uploaded_file.getvalue()))
            else:
                unsuitable_files.append((uploaded_file.name, uploaded_file.getvalue()))
            
            # Create a download link
            encoded_bytes = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
            resume_link = f'<a href="data:application/octet-stream;base64,{encoded_bytes}" download="{uploaded_file.name}">Download</a>'

            results.append({
                "name": uploaded_file.name,
                "suitability": suitability,
                "link": resume_link
            })

            # Save resume to database
            insert_resume(uploaded_file.name, text, uploaded_file.getvalue())

        except Exception as e:
            st.error(f"Error processing resume '{uploaded_file.name}': {str(e)}")
            continue

    # Display the analysis results
    if results:
        st.write("### Analysis Results")
        st.write("You can click on the 'Download' link to view the resume.")
        
        # Create the table
        table_html = "<table class='result-table'><thead><tr><th>Name of the Resume</th><th>Suitability</th><th>Resume Link</th></tr></thead><tbody>"
        for result in results:
            suitability_class = "suitable" if result['suitability'] == "Suitable" else "not-suitable"
            table_html += f"<tr><td>{result['name']}</td><td class='{suitability_class}'>{result['suitability']}</td><td>{result['link']}</td></tr>"
        table_html += "</tbody></table>"
        st.markdown(table_html, unsafe_allow_html=True)

    # Create download buttons for suitable and unsuitable files
    if suitable_files:
        suitable_zip = create_zip_download(suitable_files, "Suitable_Resumes.zip")
        st.download_button(
            label="Download Suitable Resumes",
            data=suitable_zip,
            file_name="Suitable_Resumes.zip",
            mime="application/zip"
        )

    if unsuitable_files:
        unsuitable_zip = create_zip_download(unsuitable_files, "Unsuitable_Resumes.zip")
        st.download_button(
            label="Download Unsuitable Resumes",
            data=unsuitable_zip,
            file_name="Unsuitable_Resumes.zip",
            mime="application/zip"
        )

# Upload to Database button
if st.button("Upload to Database") and uploaded_files:
    for uploaded_file in uploaded_files:
        try:
            if uploaded_file.type == "application/pdf":
                text = input_pdf_text(uploaded_file)
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                text = input_docx_text(uploaded_file)
            
            # Check if a file with the same name and content already exists in the database
            c.execute('SELECT name, text FROM resumes WHERE name=? AND text=?', (uploaded_file.name, text))
            result = c.fetchone()
            if result is None:
                insert_resume(uploaded_file.name, text, uploaded_file.getvalue())
                st.success(f"Uploaded {uploaded_file.name} to the database.")
            else:
                st.warning(f"File '{uploaded_file.name}' already exists in the database with the same content. Skipping upload.")
        except Exception as e:
            st.error(f"Error processing resume '{uploaded_file.name}': {str(e)}")

# Analyze Stored Data button
if st.button("Analyse Stored Data"):
    if jd:
        st.write("### Analysis Results Against New Job Description")
       
    st.write("### Analysis Results Against New Job Description")
    results = match_resumes(jd)

    if results:
        st.write("You can click on the 'Download' link to view the resume.")
        
        # Create the table
        table_html = "<table class='result-table'><thead><tr><th>Name of the Resume</th><th>Suitability</th><th>Resume Link</th></tr></thead><tbody>"
        for result in results:
            suitability_class = "suitable" if result['suitability'] == "Suitable" else "not-suitable"
            table_html += f"<tr><td>{result['name']}</td><td class='{suitability_class}'>{result['suitability']}</td><td>{result['link']}</td></tr>"
        table_html += "</tbody></table>"
        st.markdown(table_html, unsafe_allow_html=True)

    else:
        st.write("No resumes found in the database.")

else:
    st.error("Please paste a job description for analysis.")

# Show Database List Button
if st.button("Show Database List"):
    st.write("### Database List")
    resumes = fetch_resumes()
    
    # Convert data into structured format for table display
    data = [(resume[0], resume[1]) for resume in resumes]
    
    # Create a DataFrame for better formatting
    data_df = pd.DataFrame(data, columns=["Name", "Upload Date"])
    st.dataframe(data_df)

    # Download Database List as ZIP
    if resumes:
        resume_data = [(resume[0],) for resume in resumes]
        zip_buffer = create_zip_download(resume_data, "Database_Resumes.zip")
        st.download_button(
            label="Download Database List",
            data=zip_buffer,
            file_name="Database_Resumes.zip",
            mime="application/zip"
        )

# Input box and button for deleting a file from the database
st.sidebar.title("SQL Database Management")
st.sidebar.subheader("Delete Files")
delete_filename = st.sidebar.text_input("Enter Filename to Delete")
if st.sidebar.button("Delete File"):
    if delete_filename:
        delete_resume(delete_filename)
        st.sidebar.success(f"'{delete_filename}' deleted from database.")
    else:
        st.sidebar.error("Please enter a filename to delete.")

# Button to remove duplicate files from the database
if st.sidebar.button("Remove Duplicate Files"):
    remove_duplicates()
    st.sidebar.success("Duplicate files removed from the database.")

# Button to delete entire database
if st.sidebar.button("Delete Entire Database"):
    delete_database()
    st.sidebar.warning("Entire database deleted.")

# Close database connection when done
conn.close()
