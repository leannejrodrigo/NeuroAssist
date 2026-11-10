#domain weights which are used during the final score classification.
weights = {
    "Memory": 3,
    "Informant": 3,
    "Executive": 2,
    "IADL": 2,
    "Orientation": 1
}

#Assesment questions grouped by each domain
questions = {
    "Memory": [
        "How often do you need instructions repeated?",
        "Do you often forget recent conversations or events?",
        "Do you rely on notes or reminders?",
        "How often do you forget why you entered a room?"
    ],

    "Orientation": [
        "Do you rely on GPS or maps on routes you know for years?",
        "Do unfamiliar environments make you feel disoriented?",
        "How often do you lose track of the sequence of daily activities?",
        "Do you remember what day it is today/day of the week?"
    ],

    "Executive": [
        "How easy is it to organize multiple tasks in order?",
        "Do you lose focus during tasks or conversations?",
        "Do you find it hard to plan or organize tasks?",
        "Do you find it hard to complete tasks that require multiple steps?"
    ],

    "Informant": [
        "Does the patient repeat questions or statements often?",
        "Has the person become less confident managing responsibilities?",
        "Does the patient struggle to follow conversations?",
        "Does the person appear slower when processing information?"
    ],

    "IADL": [
        "Do you forget to take your medicines on time?",
        "How easy is it to keep track of appointments?",
        "Do you require more help than before with household tasks?",
        "Do you require assistance when using transport or travelling?"
    ]
}

#answer options for each question.
score_options = {
    "0 - Normal / No Impairment": 0,
    "1 - Mild Impairment": 1,
    "2 - Moderate Impairment": 2,
    "3 - Severe Impairment": 3
}
