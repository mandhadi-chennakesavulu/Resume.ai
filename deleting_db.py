import sqlite3

# Connect to the database
conn = sqlite3.connect('resumes.db')
c = conn.cursor()

# Function to remove a file from the database
def remove_file(filename):
    c.execute('DELETE FROM resumes WHERE name=?', (filename,))
    conn.commit()
    print(f"File '{filename}' has been removed from the database.")

# Example: Remove a file named 'example_resume.pdf'
remove_file('Arjun[5_8].docx')

# Close the database connection
conn.close()
