# Libraries used for Streamlit interface, results table, database, JSON storage, charts, and PDF reports
import streamlit as st
import pandas as pd
import sqlite3
import json
import io
import matplotlib.pyplot as plt

# PDF report libraries
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image,
        KeepTogether
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# importing the data and scoring engine
from data import weights, questions, score_options
from engine import calculate_results


# page setup for Streamlit
st.set_page_config(
    page_title="Prodromal Dementia Screening System",
    layout="wide"
)

st.markdown(
    """
    <script>
    window.scrollTo(0, 0);
    </script>
    """,
    unsafe_allow_html=True
)


DATABASE_NAME = "neuroassist_records.db"

SEVERITY_MAP = {
    "Normal / No Impairment": 0,
    "Mild Impairment": 1,
    "Moderate Impairment": 2,
    "Severe Impairment": 3
}

RULE_NAMES = [
    ("R1", "Memory Impairment"),
    ("R2", "Informant Concern"),
    ("R3", "Executive Function Difficulty"),
    ("R4", "Orientation Concern"),
    ("R5", "IADL Impairment"),
    ("R6", "Memory + Informant Pattern"),
    ("R7", "Cognitive + Functional Pattern"),
]


def go_to(page_name):
    st.session_state.page = page_name


def create_database():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patient_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT,
            patient_id TEXT,
            age_range TEXT,
            gender TEXT,
            assessment_date TEXT,
            assessor_name TEXT,
            informant_available TEXT,
            final_risk_score REAL,
            risk_classification TEXT,
            recommendation TEXT,
            clinical_findings TEXT,
            triggered_rules TEXT,
            questionnaire_answers TEXT,
            domain_results TEXT
        )
    """)

    conn.commit()
    conn.close()


def load_records():
    create_database()
    conn = sqlite3.connect(DATABASE_NAME)
    records = pd.read_sql_query("SELECT * FROM patient_records", conn)
    conn.close()
    return records


def save_patient_info():
    st.session_state["patient_info"] = {
        "patient_name": st.session_state.get("patient_name", "N/A"),
        "patient_id": st.session_state.get("patient_id", "N/A"),
        "age_range": st.session_state.get("age_range", "N/A"),
        "gender": st.session_state.get("gender", "N/A"),
        "assessment_date": st.session_state.get("assessment_date", "N/A"),
        "assessor_name": st.session_state.get("assessor_name", "N/A"),
        "informant_available": st.session_state.get("informant_available", "N/A"),
    }


def save_questionnaire_answers():
    answers = {}

    for domain, qs in questions.items():
        for i in range(1, len(qs) + 1):
            key = f"{domain}_{i}"
            answers[key] = st.session_state.get(key, "0 - Normal / No Impairment")

    st.session_state["questionnaire_answers"] = answers


def save_patient_record(patient_info, display_score, risk, recommendation, findings, triggered_rules, results):
    create_database()

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO patient_records (
            patient_name,
            patient_id,
            age_range,
            gender,
            assessment_date,
            assessor_name,
            informant_available,
            final_risk_score,
            risk_classification,
            recommendation,
            clinical_findings,
            triggered_rules,
            questionnaire_answers,
            domain_results
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        patient_info.get("patient_name", "N/A"),
        patient_info.get("patient_id", "N/A"),
        patient_info.get("age_range", "N/A"),
        patient_info.get("gender", "N/A"),
        str(patient_info.get("assessment_date", "N/A")),
        patient_info.get("assessor_name", "N/A"),
        patient_info.get("informant_available", "N/A"),
        display_score,
        risk,
        recommendation,
        " | ".join(findings) if findings else "None",
        " | ".join(triggered_rules) if triggered_rules else "None",
        json.dumps(st.session_state.get("questionnaire_answers", {})),
        json.dumps(results)
    ))

    conn.commit()
    conn.close()


def build_rule_summary(triggered_rules):
    rule_summary = []

    for rule_code, rule_name in RULE_NAMES:
        status = "✅ Triggered" if any(rule_code in rule for rule in triggered_rules) else "❌ Not Triggered"
        rule_summary.append({
            "Rule": rule_code,
            "Clinical Finding": rule_name,
            "Status": status
        })

    return pd.DataFrame(rule_summary)


def build_questionnaire_answer_table(saved_answers):
    answer_rows = []

    for key, answer in saved_answers.items():
        try:
            domain, question_number = key.rsplit("_", 1)
            question_index = int(question_number) - 1
            question_text = questions[domain][question_index]
        except Exception:
            domain = key
            question_number = "-"
            question_text = "N/A"

        answer_rows.append({
            "Domain": domain,
            "Question": f"Q{question_number}",
            "Question Text": question_text,
            "Selected Answer": answer
        })

    return pd.DataFrame(answer_rows)


def build_domain_chart_data(domain_results):
    chart_rows = []

    for row in domain_results:
        chart_rows.append({
            "Domain": row["Domain"],
            "Severity Level": SEVERITY_MAP.get(row["Severity"], 0)
        })

    return pd.DataFrame(chart_rows)


def get_follow_up_recommendation(risk):
    if risk == "High Risk":
        return "Immediate specialist referral is recommended. Further diagnostic evaluation should be considered."
    elif risk == "Moderate Risk":
        return "Further monitoring is recommended. A follow-up assessment may be considered within 6 months."
    else:
        return "Routine monitoring is recommended. Reassessment may be considered if concerns persist."


def get_change_label(previous_score, current_score):
    if current_score > previous_score:
        return "⬆ Increased"
    elif current_score < previous_score:
        return "⬇ Reduced"
    else:
        return "➡ Stable"


def get_risk_badge(risk):
    if risk == "High Risk":
        return "🔴 High Risk"
    elif risk == "Moderate Risk":
        return "🟡 Moderate Risk"
    else:
        return "🟢 Low Risk"


def get_informant_note(informant_available):
    if informant_available == "No":
        return (
            "No. Informant input was not available during this assessment. "
            "Clinical interpretation should consider obtaining information from a family member or caregiver where possible."
        )
    else:
        return (
            "Yes. Informant input was available and contributed to the assessment."
        )


def create_domain_severity_chart_image(domain_results):
    chart_data = build_domain_chart_data(domain_results)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(chart_data["Domain"], chart_data["Severity Level"])
    ax.set_xlabel("Severity Level")
    ax.set_ylabel("Assessment Domain")
    ax.set_title("Domain Severity Overview")
    ax.set_xlim(0, 3)
    ax.set_xticks([0, 1, 2, 3])
    ax.set_xticklabels(["Normal", "Mild", "Moderate", "Severe"])

    for i, value in enumerate(chart_data["Severity Level"]):
        ax.text(value + 0.05, i, str(value), va="center", fontsize=9)

    plt.tight_layout()

    image_buffer = io.BytesIO()
    plt.savefig(image_buffer, format="png", dpi=150)
    plt.close(fig)
    image_buffer.seek(0)

    return image_buffer


def create_risk_trend_chart_image(patient_history):
    history = patient_history.copy()
    history["assessment_date"] = pd.to_datetime(history["assessment_date"], errors="coerce")
    history = history.sort_values(["assessment_date", "id"])

    fig, ax = plt.subplots(figsize=(7, 4))

    ax.plot(
        history["assessment_date"],
        history["final_risk_score"],
        marker="o",
        linewidth=2
    )

    for x, y in zip(history["assessment_date"], history["final_risk_score"]):
        ax.text(
            x,
            y + 0.25,
            f"{y:.1f}",
            ha="center",
            fontsize=9
        )

    latest_risk = history.iloc[-1]["risk_classification"]
    latest_score = history.iloc[-1]["final_risk_score"]

    ax.text(
        0.02,
        0.95,
        f"Current Status: {get_risk_badge(latest_risk)} ({latest_score:.1f}/11)",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8)
    )

    ax.set_xlabel("Assessment Date")
    ax.set_ylabel("Final Risk Score")
    ax.set_title("Risk Score Trend Over Time")
    ax.set_ylim(0, 11)
    ax.grid(True)

    plt.xticks(rotation=30)
    plt.tight_layout()

    image_buffer = io.BytesIO()
    plt.savefig(image_buffer, format="png", dpi=150)
    plt.close(fig)
    image_buffer.seek(0)

    return image_buffer


def generate_pdf_report(selected_record, patient_history):
    if not REPORTLAB_AVAILABLE:
        return None

    pdf_buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=35,
        leftMargin=35,
        topMargin=35,
        bottomMargin=35
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    normal_style = styles["BodyText"]

    small_style = ParagraphStyle(
        "Small",
        parent=normal_style,
        fontSize=8,
        leading=10
    )

    story = []

    domain_results = json.loads(selected_record["domain_results"])
    saved_answers = json.loads(selected_record["questionnaire_answers"])
    triggered_rules = selected_record["triggered_rules"]
    clinical_findings = selected_record["clinical_findings"]
    informant_note = get_informant_note(selected_record["informant_available"])

    story.append(Paragraph("NeuroAssist Clinical Assessment Report", title_style))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Patient Information", heading_style))

    patient_table = Table([
        ["Patient Name", Paragraph(str(selected_record["patient_name"]), normal_style)],
        ["Patient ID", Paragraph(str(selected_record["patient_id"]), normal_style)],
        ["Age Range", Paragraph(str(selected_record["age_range"]), normal_style)],
        ["Gender", Paragraph(str(selected_record["gender"]), normal_style)],
        ["Assessment Date", Paragraph(str(selected_record["assessment_date"]), normal_style)],
        ["Assessor", Paragraph(str(selected_record["assessor_name"]), normal_style)],
        ["Informant Information", Paragraph(informant_note, normal_style)],
    ], colWidths=[170, 290])

    patient_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))

    story.append(patient_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Assessment Summary", heading_style))

    summary_table = Table([
        ["Final Risk Score", Paragraph(f"{selected_record['final_risk_score']} / 11", normal_style)],
        ["Risk Classification", Paragraph(str(selected_record["risk_classification"]), normal_style)],
        ["Recommendation", Paragraph(str(selected_record["recommendation"]), normal_style)],
        ["Suggested Follow-up", Paragraph(get_follow_up_recommendation(selected_record["risk_classification"]), normal_style)],
    ], colWidths=[170, 290])

    summary_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Domain Score Summary", heading_style))

    domain_table_data = [["Domain", "Raw Score", "Normalized", "Severity", "Weight", "Weighted Score"]]

    for row in domain_results:
        domain_table_data.append([
            Paragraph(str(row["Domain"]), small_style),
            Paragraph(str(row["Raw Score"]), small_style),
            Paragraph(str(row["Normalized Score"]), small_style),
            Paragraph(str(row["Severity"]), small_style),
            Paragraph(str(row["Weight"]), small_style),
            Paragraph(str(row["Weighted Score"]), small_style)
        ])

    domain_table = Table(domain_table_data, colWidths=[75, 60, 70, 130, 50, 80])

    domain_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
    ]))

    story.append(domain_table)
    story.append(Spacer(1, 14))

    domain_chart = create_domain_severity_chart_image(domain_results)

    story.append(
        KeepTogether([
            Paragraph("Domain Severity Chart", heading_style),
            Spacer(1, 6),
            Image(domain_chart, width=450, height=250),
            Spacer(1, 14)
        ])
    )

    if len(patient_history) > 1:
        risk_chart = create_risk_trend_chart_image(patient_history)

        story.append(
            KeepTogether([
                Paragraph("Risk Trend Chart", heading_style),
                Spacer(1, 6),
                Image(risk_chart, width=450, height=250),
                Spacer(1, 14)
            ])
        )

    story.append(Paragraph("Clinical Findings", heading_style))
    story.append(Paragraph(clinical_findings.replace(" | ", "<br/>"), normal_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Triggered Rules", heading_style))
    story.append(Paragraph(triggered_rules.replace(" | ", "<br/>"), normal_style))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Referral Summary", heading_style))

    referral_text = f"""
    Patient {selected_record['patient_name']} ({selected_record['patient_id']}) was assessed using NeuroAssist on {selected_record['assessment_date']}.
    The final weighted score was {selected_record['final_risk_score']} out of 11, classified as {selected_record['risk_classification']}.
    Informant Information: {informant_note}
    Clinical findings identified: {clinical_findings}.
    Triggered rules: {triggered_rules}.
    Recommendation: {selected_record['recommendation']}.
    Suggested follow-up: {get_follow_up_recommendation(selected_record['risk_classification'])}
    """

    story.append(Paragraph(referral_text, normal_style))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Questionnaire Responses", heading_style))

    answer_table_df = build_questionnaire_answer_table(saved_answers)

    answer_table_data = [["Domain", "Question", "Selected Answer"]]

    for _, row in answer_table_df.iterrows():
        answer_table_data.append([
            Paragraph(str(row["Domain"]), small_style),
            Paragraph(str(row["Question"]), small_style),
            Paragraph(str(row["Selected Answer"]), small_style)
        ])

    answer_table = Table(answer_table_data, colWidths=[100, 60, 300])

    answer_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
    ]))

    story.append(answer_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph(
        "Disclaimer: NeuroAssist is intended to support screening and referral decisions. It does not provide a medical diagnosis and should not replace clinical judgement.",
        small_style
    ))

    doc.build(story)
    pdf_buffer.seek(0)

    return pdf_buffer


def load_demo_scenario(scenario):
    demo_answers = {
        "Low Risk": {
            "Memory": [0, 0, 0, 0],
            "Orientation": [0, 0, 0, 0],
            "Executive": [0, 0, 0, 0],
            "Informant": [0, 0, 0, 0],
            "IADL": [0, 0, 0, 0],
        },
        "Moderate Risk": {
            "Memory": [2, 2, 2, 1],
            "Orientation": [1, 1, 0, 0],
            "Executive": [1, 1, 1, 1],
            "Informant": [2, 2, 2, 1],
            "IADL": [1, 1, 1, 1],
        },
        "High Risk": {
            "Memory": [3, 3, 3, 2],
            "Orientation": [2, 2, 1, 1],
            "Executive": [2, 2, 2, 2],
            "Informant": [3, 3, 3, 2],
            "IADL": [3, 3, 2, 2],
        }
    }

    reverse_score_options = {value: key for key, value in score_options.items()}

    for domain, scores in demo_answers[scenario].items():
        for i, score in enumerate(scores, start=1):
            st.session_state[f"{domain}_{i}"] = reverse_score_options[score]

    st.session_state["patient_name"] = f"Demo Patient - {scenario}"
    st.session_state["patient_id"] = scenario.replace(" ", "-").upper()
    st.session_state["assessor_name"] = "Demo GP"
    st.session_state["informant_available"] = "Yes"

    save_questionnaire_answers()
    save_patient_info()
    go_to("3. Questionnaire")


if "page" not in st.session_state:
    st.session_state.page = "1. Welcome Screen"


# PAGE 1: Welcome Screen
if st.session_state.page == "1. Welcome Screen":

    st.title("Welcome to NeuroAssist")
    st.subheader("Prodromal Dementia Clinical Decision Support System")

    st.markdown("---")

    st.header("System Overview")

    st.write(
        "NeuroAssist supports general practitioners in screening for possible "
        "prodromal dementia risk using structured questionnaire responses, weighted "
        "scoring, and rule-based reasoning."
    )

    st.info(
        "This system is intended to support clinical decision-making and referral decisions. "
        "It does not provide a medical diagnosis."
    )

    st.markdown("---")

    st.header("Assessment Domains")

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Memory", "4 Questions")
    col2.metric("Informant", "4 Questions")
    col3.metric("Executive", "4 Questions")
    col4.metric("IADL", "4 Questions")
    col5.metric("Orientation", "4 Questions")

    st.markdown("---")

    st.header("Quick Actions")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Start Assessment"):
            go_to("2. Patient Information")
            st.rerun()

    with col2:
        if st.button("📂 Patient Records"):
            go_to("5. Patient Records")
            st.rerun()

    st.markdown("---")

    st.subheader("Demo Scenarios")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Load Low Risk Demo"):
            load_demo_scenario("Low Risk")
            st.rerun()

    with col2:
        if st.button("Load Moderate Risk Demo"):
            load_demo_scenario("Moderate Risk")
            st.rerun()

    with col3:
        if st.button("Load High Risk Demo"):
            load_demo_scenario("High Risk")
            st.rerun()


# PAGE 2: Patient Information
elif st.session_state.page == "2. Patient Information":

    st.caption("NeuroAssist")
    st.header("Patient / Assessment Information")

    st.write("Please enter the patient's information and assessment details below.")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input("Patient Name", placeholder="Enter patient name", key="patient_name")
        st.text_input("Patient code/ID", placeholder="Example: P000", key="patient_id")
        st.selectbox("Age Range", ["Below 50", "50–59", "60–69", "70–79", "80+"], key="age_range")

    with col2:
        st.text_input("Assessor Name", placeholder="Enter assessor name", key="assessor_name")
        st.selectbox("Gender", ["Male", "Female", "Prefer not to say"], key="gender")
        st.selectbox("Informant Available?", ["Yes", "No"], key="informant_available")

    st.date_input("Assessment Date", key="assessment_date")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Back to Dashboard"):
            go_to("1. Welcome Screen")
            st.rerun()

    with col2:
        if st.button("Continue to Questionnaire"):
            save_patient_info()
            go_to("3. Questionnaire")
            st.rerun()


# PAGE 3: Questionnaire
elif st.session_state.page == "3. Questionnaire":

    st.caption("NeuroAssist")
    st.header("Questionnaire Assessment")

    if "questionnaire_answers" in st.session_state:
        for key, value in st.session_state["questionnaire_answers"].items():
            if key not in st.session_state:
                st.session_state[key] = value

    st.write("Please answer the following questions based on the patient's current cognitive and functional status.")

    st.info(
        "Scoring Interpretation: 0 = Normal / No Impairment, 1 = Mild Impairment, "
        "2 = Moderate Impairment, 3 = Severe Impairment"
    )

    st.markdown("---")

    domain_icons = {
        "Memory": "🧠",
        "Informant": "👥",
        "Executive": "⚙️",
        "IADL": "🏠",
        "Orientation": "🕰️"
    }

    domain_items = list(questions.items())

    for row_start in range(0, len(domain_items), 2):
        cols = st.columns(2)

        for col_index, (domain, qs) in enumerate(domain_items[row_start:row_start + 2]):
            with cols[col_index]:
                with st.expander(f"{domain_icons.get(domain, '')} {domain} Assessment", expanded=False):
                    for i, question in enumerate(qs, start=1):
                        st.radio(
                            f"Q{i}. {question}",
                            list(score_options.keys()),
                            key=f"{domain}_{i}"
                        )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Back to Patient Information"):
            go_to("2. Patient Information")
            st.rerun()

    with col2:
        if st.button("Submit Assessment"):
            save_questionnaire_answers()
            go_to("4. Results & Recommendation")
            st.rerun()


# PAGE 4: Results & Recommendation
elif st.session_state.page == "4. Results & Recommendation":

    st.caption("NeuroAssist")
    st.header("Results and Recommendation")

    display_score, risk, recommendation, results, facts, findings, triggered_rules = calculate_results(
        st.session_state.get("questionnaire_answers", st.session_state),
        questions,
        weights,
        score_options
    )

    patient_info = st.session_state.get("patient_info", {})

    st.subheader("📋 Assessment Summary")

    st.write(f"**Patient Name:** {patient_info.get('patient_name', 'N/A')}")
    st.write(f"**Patient ID:** {patient_info.get('patient_id', 'N/A')}")
    st.write(f"**Age Range:** {patient_info.get('age_range', 'N/A')}")
    st.write(f"**Gender:** {patient_info.get('gender', 'N/A')}")
    st.write(f"**Assessment Date:** {patient_info.get('assessment_date', 'N/A')}")
    st.write(f"**Assessor:** {patient_info.get('assessor_name', 'N/A')}")
    st.write(f"**Informant Available:** {patient_info.get('informant_available', 'N/A')}")

    if patient_info.get("informant_available") == "No":
        st.warning(
            "Informant input was not available for this assessment. "
            "Input from a family member or caregiver is recommended to support further clinical review."
        )

    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    col1.metric("📊 Final Risk Score", f"{display_score:g} / 11")
    col2.metric("📈 Risk Classification", risk)

    if risk == "High Risk":
        recommendation_action = "Refer to Specialist"
    elif risk == "Moderate Risk":
        recommendation_action = "Further monitoring"
    else:
        recommendation_action = "Routine monitoring"

    col3.metric("🩺 Recommendation Action", recommendation_action)

    st.subheader("📊 Domain Score Summary")
    st.dataframe(pd.DataFrame(results), use_container_width=True)

    st.subheader("📉 Domain Severity Chart")
    chart_data = build_domain_chart_data(results)

    st.bar_chart(
        chart_data,
        x="Domain",
        y="Severity Level",
        use_container_width=True
    )

    st.caption("Severity scale: 0 = Normal, 1 = Mild, 2 = Moderate, 3 = Severe")

    st.subheader("🧠 Clinical Findings Summary")
    rule_summary_df = build_rule_summary(triggered_rules)

    st.dataframe(rule_summary_df, use_container_width=True)
    st.info(f"{len(triggered_rules)} of 7 clinical reasoning rules were triggered.")

    with st.expander("⚙️ System Reasoning Details"):
        if triggered_rules:
            for rule in triggered_rules:
                st.write(f"• {rule}")
        else:
            st.write("No clinical reasoning rules were triggered based on the assessment responses.")

    st.subheader("📖 Assessment Interpretation")

    if risk == "Low Risk":
        st.info(
            f"The final weighted score is {display_score:g} out of 11, which falls under the Low Risk range. "
            "Minimal evidence of cognitive or functional impairment was found. "
            "If concerns persist, consider routine monitoring."
        )
    elif risk == "Moderate Risk":
        st.info(
            f"The final weighted score is {display_score:g} out of 11, which falls under the Moderate Risk range. "
            "Evidence of possible cognitive or functional concerns was identified. "
            "Further monitoring or a follow-up assessment is recommended."
        )
    else:
        st.info(
            f"The final weighted score is {display_score:g} out of 11, which falls under the High Risk range. "
            "Significant evidence of cognitive or functional impairment was found."
        )

    st.subheader("📝 Recommendation")

    if risk == "High Risk":
        st.warning(recommendation)
    elif risk == "Moderate Risk":
        st.info(recommendation)
    else:
        st.success(recommendation)

    st.subheader("📅 Suggested Follow-up")
    st.info(get_follow_up_recommendation(risk))

    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Back to Questionnaire"):
            go_to("3. Questionnaire")
            st.rerun()

    with col2:
        if st.button("Start New Assessment"):
            st.session_state.clear()
            st.session_state.page = "1. Welcome Screen"
            st.rerun()

    with col3:
        if st.button("📄 Save Assessment"):
            save_patient_record(
                patient_info,
                display_score,
                risk,
                recommendation,
                findings,
                triggered_rules,
                results
            )
            st.success("Assessment saved to patient records successfully.")


# PAGE 5: Patient Records
elif st.session_state.page == "5. Patient Records":

    st.caption("NeuroAssist")
    st.header("📂 Patient Records Dashboard")

    records = load_records()

    st.subheader("🔎 Search Patient Records")

    col1, col2, col3 = st.columns(3)

    with col1:
        search_query = st.text_input(
            "Patient Name or Patient ID",
            placeholder="Enter patient name or ID"
        )

    with col2:
        risk_filter = st.selectbox(
            "Risk Classification",
            ["All", "Low Risk", "Moderate Risk", "High Risk"]
        )

    with col3:
        use_date_filter = st.checkbox("Filter by Assessment Date")
        if use_date_filter:
            selected_date = st.date_input("Assessment Date")
        else:
            selected_date = None

    search_clicked = st.button("Search Records")

    if "records_search_clicked" not in st.session_state:
        st.session_state.records_search_clicked = False

    if search_clicked:
        st.session_state.records_search_clicked = True

    if not st.session_state.records_search_clicked:
        st.info("Enter a patient name or ID, or apply a filter, then click Search Records.")

        if st.button("Back to Dashboard"):
            go_to("1. Welcome Screen")
            st.rerun()

        st.stop()

    filtered_records = records.copy()

    if search_query:
        filtered_records = filtered_records[
            filtered_records["patient_name"].astype(str).str.contains(search_query, case=False, na=False)
            |
            filtered_records["patient_id"].astype(str).str.contains(search_query, case=False, na=False)
        ]

    if risk_filter != "All":
        filtered_records = filtered_records[
            filtered_records["risk_classification"] == risk_filter
        ]

    if selected_date is not None:
        filtered_records = filtered_records[
            pd.to_datetime(filtered_records["assessment_date"], errors="coerce").dt.date == selected_date
        ]

    if filtered_records.empty:
        st.warning("No matching patient records found.")

        if st.button("Back to Dashboard"):
            go_to("1. Welcome Screen")
            st.rerun()

        st.stop()

    st.markdown("---")
    st.subheader("Search Results")

    filtered_records["assessment_date_parsed"] = pd.to_datetime(
        filtered_records["assessment_date"],
        errors="coerce"
    )

    filtered_records = filtered_records.sort_values(
        ["patient_id", "assessment_date_parsed", "id"]
    )

    st.dataframe(
        filtered_records[
            [
                "id",
                "patient_name",
                "patient_id",
                "assessment_date",
                "final_risk_score",
                "risk_classification",
                "informant_available"
            ]
        ],
        use_container_width=True
    )

    selected_record_id = st.selectbox(
        "Select an assessment record",
        filtered_records["id"].tolist()
    )

    selected_record = filtered_records[
        filtered_records["id"] == selected_record_id
    ].iloc[0]

    patient_history = records[
        (records["patient_name"] == selected_record["patient_name"])
        |
        (records["patient_id"] == selected_record["patient_id"])
    ].copy()

    patient_history["assessment_date_parsed"] = pd.to_datetime(
        patient_history["assessment_date"],
        errors="coerce"
    )

    patient_history = patient_history.sort_values(
        ["assessment_date_parsed", "id"]
    )

    selected_index_list = patient_history.index[
        patient_history["id"] == selected_record_id
    ].tolist()

    previous_record = None

    if selected_index_list:
        selected_position = patient_history.index.get_loc(selected_index_list[0])
        if selected_position > 0:
            previous_record = patient_history.iloc[selected_position - 1]

    st.markdown("---")
    st.subheader("Selected Patient Overview")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Patient", selected_record["patient_name"])
    col2.metric("Risk Status", get_risk_badge(selected_record["risk_classification"]))
    col3.metric("Score", f"{selected_record['final_risk_score']} / 11")
    col4.metric("Total Assessments", len(patient_history))

    st.write(f"**Patient ID:** {selected_record['patient_id']}")
    st.write(f"**Assessment Date:** {selected_record['assessment_date']}")
    st.write(f"**Assessor:** {selected_record['assessor_name']}")
    st.write(f"**Informant Information:** {get_informant_note(selected_record['informant_available'])}")

    if selected_record["informant_available"] == "No":
        st.warning(
            "Informant input was not available for this assessment. "
            "Clinical interpretation should consider obtaining caregiver or family input."
        )

    st.markdown("---")
    st.subheader("📈 Risk Progression Over Time")

    if len(patient_history) > 1:
        trend_df = patient_history[["assessment_date", "final_risk_score"]].copy()
        trend_df["assessment_date"] = pd.to_datetime(trend_df["assessment_date"], errors="coerce")
        trend_df = trend_df.sort_values("assessment_date")

        fig, ax = plt.subplots(figsize=(8, 4))

        ax.plot(
            trend_df["assessment_date"],
            trend_df["final_risk_score"],
            marker="o",
            linewidth=2
        )

        for x, y in zip(trend_df["assessment_date"], trend_df["final_risk_score"]):
            ax.text(
                x,
                y + 0.25,
                f"{y:.1f}",
                ha="center",
                fontsize=9
            )

        ax.text(
            0.02,
            0.95,
            f"Current Status: {get_risk_badge(selected_record['risk_classification'])} ({selected_record['final_risk_score']:.1f}/11)",
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8)
        )

        ax.set_ylim(0, 11)
        ax.set_ylabel("Risk Score")
        ax.set_xlabel("Assessment Date")
        ax.set_title("Risk Score Trend Over Time")
        ax.grid(True)

        plt.xticks(rotation=30)
        plt.tight_layout()

        st.pyplot(fig)
        plt.close(fig)

    else:
        st.info("Only one saved assessment is available for this patient. Risk trend will appear after multiple assessments are saved.")

    st.subheader("📅 Assessment History")

    history_display = patient_history[
        [
            "assessment_date",
            "final_risk_score",
            "risk_classification",
            "informant_available"
        ]
    ].copy()

    changes = []
    previous_score = None

    for _, row in history_display.iterrows():
        if previous_score is None:
            changes.append("—")
        else:
            changes.append(get_change_label(previous_score, row["final_risk_score"]))
        previous_score = row["final_risk_score"]

    history_display["Change"] = changes

    st.dataframe(history_display, use_container_width=True)

    st.subheader("🕒 Patient Timeline")

    for _, row in patient_history.iterrows():
        st.write(
            f"**{row['assessment_date']}** → "
            f"{get_risk_badge(row['risk_classification'])} "
            f"({row['final_risk_score']} / 11)"
        )

    if previous_record is not None:
        st.markdown("---")
        st.subheader("🔁 Previous vs Current Assessment")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Previous Score",
            f"{previous_record['final_risk_score']} / 11",
            previous_record["risk_classification"]
        )

        col2.metric(
            "Current Score",
            f"{selected_record['final_risk_score']} / 11",
            selected_record["risk_classification"]
        )

        score_change = selected_record["final_risk_score"] - previous_record["final_risk_score"]

        col3.metric(
            "Change",
            get_change_label(previous_record["final_risk_score"], selected_record["final_risk_score"]),
            f"{score_change:+.1f}"
        )

    st.markdown("---")
    st.subheader("📊 Selected Assessment Domain Severity")

    saved_domain_results = json.loads(selected_record["domain_results"])
    domain_chart_data = build_domain_chart_data(saved_domain_results)

    st.bar_chart(
        domain_chart_data,
        x="Domain",
        y="Severity Level",
        use_container_width=True
    )

    st.caption("Severity scale: 0 = Normal, 1 = Mild, 2 = Moderate, 3 = Severe")

    st.subheader("Domain Score Summary")
    st.dataframe(pd.DataFrame(saved_domain_results), use_container_width=True)

    st.subheader("🧠 Clinical Findings Summary")

    selected_triggered_rules = (
        [] if selected_record["triggered_rules"] == "None"
        else selected_record["triggered_rules"].split(" | ")
    )

    st.dataframe(
        build_rule_summary(selected_triggered_rules),
        use_container_width=True
    )

    st.subheader("Saved Clinical Findings")
    st.write(selected_record["clinical_findings"])

    st.subheader("Saved Triggered Rules")
    st.write(selected_record["triggered_rules"])

    st.subheader("📅 Suggested Follow-up")
    st.info(get_follow_up_recommendation(selected_record["risk_classification"]))

    with st.expander("Advanced Information: View Saved Questionnaire Answers"):
        saved_answers = json.loads(selected_record["questionnaire_answers"])
        answer_table = build_questionnaire_answer_table(saved_answers)
        st.dataframe(answer_table, use_container_width=True)

    st.markdown("---")
    st.subheader("📤 Referral Summary")

    informant_note = get_informant_note(selected_record["informant_available"])

    referral_summary = f"""
Referral Summary

Patient Name: {selected_record['patient_name']}
Patient ID: {selected_record['patient_id']}
Assessment Date: {selected_record['assessment_date']}
Assessor: {selected_record['assessor_name']}

Informant Information:
{informant_note}

Final Risk Score: {selected_record['final_risk_score']} / 11
Risk Classification: {selected_record['risk_classification']}

Clinical Findings:
{selected_record['clinical_findings']}

Triggered Rules:
{selected_record['triggered_rules']}

Recommendation:
{selected_record['recommendation']}

Suggested Follow-up:
{get_follow_up_recommendation(selected_record['risk_classification'])}

Note:
This system is intended to support screening and referral decisions. It does not provide a medical diagnosis.
"""

    st.text_area("Referral Summary", referral_summary, height=350)

    st.markdown("---")
    st.subheader("📄 Clinical Report PDF")

    if REPORTLAB_AVAILABLE:
        pdf_buffer = generate_pdf_report(selected_record, patient_history)

        st.download_button(
            label="📄 Export Clinical Report (PDF)",
            data=pdf_buffer,
            file_name=f"{selected_record['patient_id']}_NeuroAssist_Clinical_Report.pdf",
            mime="application/pdf"
        )
    else:
        st.error("PDF export requires reportlab. Install it using: pip install reportlab")

    if st.button("Back to Dashboard"):
        st.session_state.records_search_clicked = False
        go_to("1. Welcome Screen")
        st.rerun()