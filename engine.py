# normalized domain score conversion to severity level
#used by the reasoning engine.
def get_severity(normalized_score):
    if normalized_score <= 0.25:
        return "Normal / No Impairment"
    elif normalized_score <= 0.50:
        return "Mild Impairment"
    elif normalized_score <= 0.75:
        return "Moderate Impairment"
    else:
        return "Severe Impairment"
# scoring and reasoning function used by the assesment.
def calculate_results(session_state, questions, weights, score_options, informant_available=True):
#assesment outputs are stored and will be displayed on results page.
    results = []
    facts = {}
    findings = []
    triggered_rules = []
    final_score = 0
# scores are calcualated for each assesment domain.
    for domain, qs in questions.items():

        raw_score = 0

        for i in range(1, len(qs) + 1):

            selected = session_state.get(
                f"{domain}_{i}",
                "0 - Normal / No Impairment"
            )

            response_score = score_options[selected]

            raw_score += response_score
# raw score is converted to a value between 0 and 1.
        normalized_score = raw_score / 12
#severity level is determined for the domain.
        severity = get_severity(normalized_score)

        facts[domain] = severity
#domain weight is applied to show the importance in the final score.
        weighted_score = normalized_score * weights[domain]

        final_score += weighted_score

        results.append({
            "Domain": domain,
            "Raw Score": raw_score,
            "Normalized Score": f"{normalized_score:.2f}",
            "Severity": severity,
            "Weight": weights[domain],
            "Weighted Score": f"{weighted_score:.1f}"
        })

    memory_severity = facts["Memory"]
#Rule-based reasoning layer
#clinical reasoning rules
#domain severity labels are used to generate the findings and explanations.

#Individual domain rules
    if memory_severity == "Moderate Impairment":
        findings.append("Moderate memory impairment detected.")
        triggered_rules.append("R1 - Memory Impairment Rule Triggered")        
    elif memory_severity == "Severe Impairment":
        findings.append("Severe memory impairment detected.")
        triggered_rules.append("R1 - Memory Impairment Rule Triggered")   

    informant_severity = facts["Informant"]
#Individual domain rules
    if informant_severity == "Moderate Impairment":
        findings.append("Moderate informant-reported cognitive concern identified.")
        triggered_rules.append("R2 - Informant Concern Rule Triggered")
    
    elif informant_severity == "Severe Impairment":
        findings.append("Severe informant-reported cognitive concern identified.")
        triggered_rules.append("R2 - Informant Concern Rule Triggered") 
    
    executive_severity = facts["Executive"]
#Individual domain rules
    if executive_severity == "Moderate Impairment":
        findings.append("Moderate executive functioning difficulties identified.")
        triggered_rules.append("R3 - Executive Function Rule Triggered")

    elif executive_severity == "Severe Impairment":
        findings.append("Severe executive functioning difficulties identified.")
        triggered_rules.append("R3 - Executive Function Rule Triggered")
    
    orientation_severity = facts["Orientation"]
#Individual domain rules
    if orientation_severity == "Moderate Impairment":
        findings.append("Moderate orientation difficulties identified.")
        triggered_rules.append("R4 - Orientation Concern Rule Triggered")

    elif orientation_severity == "Severe Impairment":
        findings.append("Severe orientation difficulties identified.")
        triggered_rules.append("R4 - Orientation Concern Rule Triggered")

    iadl_severity = facts["IADL"]
#Individual domain rules
    if iadl_severity == "Moderate Impairment":
        findings.append("Moderate impairment in instrumental activities of daily living identified.")
        triggered_rules.append("R5 - IADL Impairment Rule Triggered")

    elif iadl_severity == "Severe Impairment":
        findings.append("Severe impairment in instrumental activities of daily living identified.")
        triggered_rules.append("R5 - IADL Impairment Rule Triggered")

#Pattern rule : memory concerns which are supported by the informant observations.
    if (
        memory_severity in ["Moderate Impairment", "Severe Impairment"]
        and
        informant_severity in ["Moderate Impairment", "Severe Impairment"]
    ):
        findings.append(
            "Combined patient and informant findings suggest possible cognitive decline."
    )
        triggered_rules.append(
            "R6 - Memory and Informant Pattern Rule Triggered"
    )


# Pattern rule : memory concerns with informant concerns and functional decline.
    if (
        memory_severity in ["Moderate Impairment", "Severe Impairment"]
        and
        informant_severity in ["Moderate Impairment", "Severe Impairment"]
        and
        iadl_severity in ["Moderate Impairment", "Severe Impairment"]
    ):
        findings.append(
            "Combined memory, informant, and functional impairment pattern identified."
    )
        triggered_rules.append(
            "R7 - Cognitive and Functional Impairment Pattern Rule Triggered"
    )

# the final weighted score is rounded for the display purposes.
    display_score = round(final_score, 1)


#classification of the overal risk using the predefined score ranges.
#risk classification rules
    if display_score <= 3.0:

        risk = "Low Risk"

        recommendation = (
            "Minimal evidence of cognitive or functional impairment "
            "was identified. Continued routine monitoring may be recommended "
            "if symptoms persist."
        )

    elif display_score <= 6.9:

        risk = "Moderate Risk"

        recommendation = (
            "Possible cognitive or functional impairment may be present. "
            "Further clinical evaluation and monitoring may be recommended."
        )

    else:

        risk = "High Risk"

        recommendation = (
            "Significant indicators of cognitive and functional impairment "
            "were identified. Referral for specialist assessment and further "
            "diagnostic evaluation is recommended."
        )
#returns all the outputs needed by the UI.        
    return display_score, risk, recommendation, results, facts, findings, triggered_rules