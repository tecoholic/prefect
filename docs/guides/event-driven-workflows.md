---
description: Run a work flow in response to custom events with an automation.
tags:
    - events
    - webhooks
    - automations
    - event-based workflows
search:
  boost: 2
---

# Event-driven workflows  TK cloud logo maybe

Event-driven workflows are a powerful workflow pattern made possible by Prefect Cloud.
In this guide we'll use a custom webhook to create events that will trigger a deployment run through an automation.

To demonstrate, we'll create an automation that runs when a GitHub issue is opened in a repository.

## Steps

1. Create a GitHub JSON webhook to send us GitHub issue data
1. Create a Prefect webhook for the GitHub JSON webhook to hit to create events with data in Prefect
1. Create an automation with an event trigger that will fire when an issue is created and the webhook endpoint is hit
1. Write Python script that will run our code and create a deployment
1. Question - do we want to push the code to GitHub and fetch it from Gitub in .serve?
1. Question - should we use Marvin or shy away?

TK update image location
![cloud-dashboard.png](https://prod-files-secure.s3.us-west-2.amazonaws.com/0e13c6a5-488b-465f-8706-5d28cb77db16/4a290013-c856-4d48-a882-106ae310f9e0/cloud-dashboard.png)

## Prerequisites

1. [Prefect installed](/getting-started/installation/) in a virtual environment
1. A [Prefect Cloud](https://app.prefect.cloud/) account. This guide uses [Webhooks](/guides/webhooks/) and [Automations](/concepts/automations/), which are Prefect Cloud features.
1. A GitHub account and access to a GitHub repository where you have permission to create a JSON webhook.

## Setup

### Install

Authenticate your CLI to Prefect Cloud with `prefect cloud login`.
Click the button in the browser window that pops up to authenticate or [create an API key manually](/cloud/users/api-keys/).

## Create a JSON webhook

Let’s create a JSON [webhook](https://docs.github.com/en/webhooks-and-events/webhooks/about-webhooks) in our <https://github.com/PrefectHQ/> TK repo name GitHub repository **that uses a Prefect webhook address. When an issue is opened the webhook will send a payload to Prefect with the issue number, title, body, and user name.

In the Prefect UI, create a webhook using the **Dynamic** template as a base.

TK image
![Screenshot 2023-08-29 at 5.02.09 PM.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/21ac713a-d850-4fe8-bff2-235aa114dd8d/Screenshot_2023-08-29_at_5.02.09_PM.png)

In the `resource` field, set the event’s name to the issue title.
We'll also include other relevant information we might use in our flow code.

```json
{
    "event": "github.issue.changed",
    "resource": {
        "prefect.resource.id": "github.issue.{{ payload.issue.number }}",
        "action": "{{ payload.action }}",
        "title": "{{ payload.issue.title }}",
        "body": "{{ payload.issue.body }}",
        "number": "{{ payload.issue.number }}",
        "user": "{{ payload.issue.user.name }}"
}
    }
```

Copy the webhook address from Prefect Cloud.

In the GitHub repo navigate to **Settings→Webhooks-Add webhook** and paste the webhook address into the **Payload URL** field.
The screenshot below shows our webhook URL, but you’ll want to use your unique webhook URL.

TK update
![Screenshot 2023-08-29 at 4.54.45 PM.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/13175bb5-6567-405b-8412-6f7fb9a987b9/Screenshot_2023-08-29_at_4.54.45_PM.png)

In the GitHub repo let's limit the scope of what this webhook can send.

Check the boxes: **Let me select individual events** and **Enable SSL verification**. Choose the **Issues** individual event.

Create the webhook and click on the **Recent Deliveries** tab.
Momentarily, you should see a successful test ping.
Create an issue in the GitHub repo and you should see another successful delivery.

TK SS
![Screenshot 2023-08-29 at 5.15.51 PM.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/309095aa-9580-4db8-987b-bc82b856b754/Screenshot_2023-08-29_at_5.15.51_PM.png)

Boom, we’re in business!

On the Prefect Cloud side, check out the **Event Feed** tab in the UI and you should see events from GitHub!

TK update image
![Screenshot 2023-08-30 at 2.02.51 PM.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/469246ae-3c1c-40dc-a3cd-082442e80a36/Screenshot_2023-08-30_at_2.02.51_PM.png)

Click on an individual event’s title and then the **Raw** tab to get all the details, including the raw payload.

TK update image
![Screenshot 2023-08-30 at 2.05.47 PM.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/f1ac4b9c-ebf4-4819-aece-437fc33af2ab/Screenshot_2023-08-30_at_2.05.47_PM.png)

Now let’s write some Python code to do something with this event data.

## Python code

The code for this project can be found in the same GitHub repo where we created our webhook: <https://github.com/PrefectHQ/Project-2-TPV-GTM-Relay>. TK address

The completed script grabs the useful info from GitHub issue.
A response is then posted to the GitHub issue.

```json
import os
import json
import requests
from prefect import flow, task, get_run_logger


@task
def issue_comment(owner: str, repo: str, issue_number: str, message: dict):
    """Send the issue comment to GitHub"""
    github_api_key = os.environ["GITHUB_API_KEY"]
    token = f"Bearer {github_api_key}"
    header = {
        "Authorization": token
    }
    requests.post(f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments",json=message, headers=header)

@flow
def suggested_fix_from_marvin(issue_number: int, issue_text: str, user_login_name: str) -> None:
    open_api_key = os.environ["OPENAI_API_KEY"]
    marvin.settings.openai.api_key = open_api_key
    
    summary = summarize_github_issue(issue_text)
    response = marvin_response(summary)

    if response:
        message = {"body": response}
        issue_comment("PrefectHQ", "Project-2-TPV-GTM-Relay", issue_number, message)
    
    return None
```

Let’s break this down.

Let’s first look at our flow-decorated function named `pipeline` that acts as our assembly function.
This function takes an issue number, issue text, and user login (name) as parameters.

These argument values will be fed in from the Prefect automation that we will create.
This automation will use use the data from the Prefect event that is created when the Prefect webhook endpoint is hit.

The response message is returned to the calling flow function and saved in the `response` variable.
The response is then logged to Prefect Cloud and saved as the value for the `body` key in the `message` dictionary.

The `issue_comment` task function is then called with the relevant information.
The GitHub API key generated by the user and saved in an environment variable is passed as the authorization token when the POST request is sent to GitHub.
Instead of an environment variable, you could use a [Prefect Secret block](https://docs.prefect.io/latest/api-ref/prefect/blocks/system/#prefect.blocks.system.Secret) to store the API key.
This alternative obfuscates the value of these API keys.
You can learn more about blocks [here](https://docs.prefect.io/latest/concepts/blocks/).

Let’s specify the environment variables we need in our script and the packages we need beyond Prefect, which is included in the Prefect-maintained Docker image. Environment variables:

`{"GITHUB_API_KEY":"abc123","OPENAI_API_KEY":"abc123","EXTRA_PIP_PACKAGES":"`

## Run the Python script

Let's create a deployment with our flow code and start a long-running process with `flow.serve`.

```bash
python gh_response.py
```

## Create an automation in Prefect Cloud

Let’s create an automation in the Prefect UI to run the deployment when the event (an issue was created) is received at the webhook URL. Automations create an action in response to a trigger.

The trigger event can be seen in the **Event Feed** tab in Prefect Cloud.

There are several ways to create an automation. The quickest is probably to click on the event in the event feed and select **Automate** from the three dot menu in the top right of the page. We’ll then be in the **Automations/Create** page with our trigger field pre-populated.

Our custom trigger type will match on any Prefect events with a resource id that start with `github.issue`. Here’s the specification:

```json
{
  "match": {
    "prefect.resource.id": "github.issue.*"
  },
  "match_related": {},
  "after": [],
  "expect": [],
  "for_each": [
    "github.issue"
  ],
  "posture": "Reactive",
  "threshold": 1,
  "within": 0
}
```

Next, let’s head to step 2 in our Automation, **Actions.** We’ll set our automation to run our deployment with the parameter values from the event. In other words, the issue number, issue text, and user login (name) parameter values for the entrypoint flow are passed from the event through the automation.

![Screenshot 2023-08-30 at 3.03.59 PM.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/e26b4721-ce7a-4aed-bf3c-dc3802ae05d5/Screenshot_2023-08-30_at_3.03.59_PM.png)

In particular, we need to specify the dynamic values from our webhook event in JSON using Jinja2 templating, so that means we want these three values on the JSON tab:
`{{ payload.issue.number }}`, `{{ payload.issue.body }}`, and `{{ payload.issue.user.name }}`

## Test it

File an issue in the GitHub repository and you should soon see a response from Marvin!

See the screenshot below where Mason passed in a less-then helpful issue and Marvin, through Rob’s API key, responded with some information that makes the best of it. 🙂

![Screenshot 2023-08-30 at 1.24.51 PM.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/f4826723-7d47-4d0a-9b65-2ce68d19531e/Screenshot_2023-08-30_at_1.24.51_PM.png)

You can check out all the details of the whole webhook → flow run sequence in the Prefect Cloud UI.

![Screenshot 2023-08-30 at 2.28.42 PM.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/e32fe995-05f8-469a-a2e5-4a7ac19bc8ac/Screenshot_2023-08-30_at_2.28.42_PM.png)

## Wrap

In this guide you’ve seen how to leverage the power of Prefect and Marvin to create event-driven workflows in response to new GitHub issues. You saw how to You can apply a similar setup to other GitHub events, such as summarizing new pull requests.

We can’t wait to see what you build with Prefect and Marvin. Happy engineering!

*Prefect makes complex workflows simpler, not harder. Try [Prefect Cloud](https://app.prefect.cloud/) for free for yourself, download our [open source package](https://github.com/PrefectHQ/prefect), join our [Slack community](https://www.prefect.io/slack/), or [talk to one of our engineers](https://calendly.com/prefect-experts/prefect-product-advocates) to learn more.*

## Next steps

Dig deeper into events, automations, or deployments TK
