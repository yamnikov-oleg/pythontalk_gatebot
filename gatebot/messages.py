GETTING_STARTED = (
    "Hello fellow pythonista!\n\n"
    "You're going to be presented with {questions_total} randomly picked "
    "questions about Python. To pass the test and be able to chat "
    "you'll have to answer correctly {answers_required} of them.\n\n"
    "When you're ready, press 'Start the quiz'.\n\n"
    "Good luck!")

# Sent when users attempts to restart an unfinished quiz.
ALREADY_STARTED = "You have already started the quiz."

# Sent when user passes the quiz and when they attempt to start the quiz again
# after passing it.
PASSED = (
    "You have passed the quiz with the result of {result}/{total}. "
    "You can now chat in the group.\n\n"
    "Click the button below to publish your result for other "
    "group members to see, if you want it.")

RESULT_SHARE = (
    "{user} has just passed the quiz with the result of {result}/{total}.\n"
    "Welcome to the group!")

# Sent when user fails the quiz and when they attempt to start the quiz again
# too soon after failing it.
FAILED = (
    "Unfortunately you have failed with the result of {result}/{total}, "
    "which is not enough to pass ({required}). But no worries, you can try "
    "again in {wait_hours} hours.\n\n"
    "When the time has passed, click /start to try again.")
