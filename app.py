import streamlit as st
import psycopg2

st.title("BitProof")
st.caption("Hello app: checking the Supabase connection")

if st.button("Test database connection"):
    try:
        conn = psycopg2.connect(st.secrets["DB_URL"])
        cur = conn.cursor()
        cur.execute(
            "select extname, extversion from pg_extension where extname = 'vector';"
        )
        row = cur.fetchone()
        conn.close()
        if row:
            st.success(f"Connected. pgvector {row[1]} is enabled.")
        else:
            st.warning("Connected, but the vector extension is not enabled.")
    except Exception as e:
        st.error(f"Connection failed: {e}")