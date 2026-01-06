import os
import json
import requests
from github import Github, Auth

GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
REPO_NAME = os.environ['GITHUB_REPOSITORY']

# Get PR number from event payload
with open(os.environ['GITHUB_EVENT_PATH'], 'r') as f:
    event = json.load(f)
PR_NUMBER = event['number']

# Use new Auth method for PyGithub
auth = Auth.Token(GITHUB_TOKEN)
g = Github(auth=auth)
repo = g.get_repo(REPO_NAME)
pr = repo.get_pull(int(PR_NUMBER))
files = pr.get_files()

# Fetch PR description
pr_description = pr.body or ""

# Fetch PR review comments (inline code comments)
review_comments = pr.get_review_comments()
review_comments_text = "\n".join(
    [f"{c.user.login}: {c.body}" for c in review_comments]
)

# Fetch PR issue comments (general discussion)
issue_comments = pr.get_issue_comments()
issue_comments_text = "\n".join(
    [f"{c.user.login}: {c.body}" for c in issue_comments]
)

# Combine all context
pr_context = f"""
PR Description:
{pr_description}

Review Comments:
{review_comments_text}

Discussion Comments:
{issue_comments_text}
"""

changes = ""
for file in files:
    if file.patch:
        changes += f"File: {file.filename}\n{file.patch}\n"

rules = """
- Consider the PR description and all PR comments for additional context, and ensure that any questions or concerns raised there are addressed in the code or in your review.
- Check if there are no conflicts.
- Check that package/email_notification.zip is updated with all new code changes.
- Check for TODO comments left in code.
- Warn if any print statements are present in production code.
- Check for unused imports.
- Use default python recommendations to improve code
- Check potential security issues
"""

gemini_url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"
headers = {"Content-Type": "application/json"}
params = {"key": GEMINI_API_KEY}
prompt = f"""
You are a code reviewer. Analyze the following PR changes according to these rules:
{rules}

PR context (description and comments):
{pr_context}

PR changes:
{changes}

If you find any issues, write a GitHub comment. If not, reply 'No issues found.'
"""

data = {
    "contents": [
        {
            "parts": [
                {"text": prompt}
            ]
        }
    ]
}

response = requests.post(gemini_url, headers=headers, params=params, json=data)
if response.status_code != 200:
    print("Gemini API error:", response.text)
    exit(1)

result = response.json()
comment = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

if "No issues found" not in comment:
    pr.create_issue_comment(comment)
else:
    print("No issues found by Gemini.")