import pandas as pd
import streamlit as st

# Function to load Excel data
def load_data(file):
    return pd.read_excel(file, engine='openpyxl')

# Function to execute query
def query_data(df, column, query):
    try:
        return df[df[column].str.contains(query, case=False, na=False)]
    except Exception as e:
        st.error(f"Error processing query: {e}")
        return pd.DataFrame()

# Streamlit App
st.title("Excel Query Tool")

uploaded_file = st.file_uploader("Choose an Excel file", type="xlsx")

if uploaded_file:
    df = load_data(uploaded_file)
    st.success("File successfully loaded!")

    # Show a sample of the data
    st.subheader("Data Preview")
    st.dataframe(df.head())

    # Allow user to select column and input query
    column = st.selectbox("Select column to query", df.columns)
    query = st.text_input(f"Enter query for {column}")

    # Query data
    if query:
        result_df = query_data(df, column, query)
        st.subheader("Query Results")
        st.dataframe(result_df)

        # Download option for query results
        st.download_button(
            label="Download query results as CSV",
            data=result_df.to_csv(index=False).encode('utf-8'),
            file_name="query_results.csv",
            mime='text/csv',
        )
