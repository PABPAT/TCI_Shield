TCI Shield — Deployment Flow
Prerequisites

GitHub account with repository PABPAT/TCI_Shield
HuggingFace account
AWS account with Bedrock access


Step 1 — Create HuggingFace Space

Go to https://huggingface.co/new-space
Fill in:

Owner: PABPAT
Space name: TCI_Shield
SDK: Docker
Template: Streamlit
Hardware: CPU Basic (Free)
Visibility: Public


Click Create Space


Step 2 — Create HuggingFace Token

Go to https://huggingface.co/settings/tokens
Click New Token

Name: TCI_Shield
Type: Write


Copy the token
Login via CLI:

bashhf auth login --force

Select y for git credential


Step 3 — Add Token to GitHub Secrets

Go to https://github.com/PABPAT/TCI_Shield/settings/secrets/actions
Click New repository secret

Name: TCI_SHIELD_HUGGING_FACE
Value: your HuggingFace token


Click Add secret


Step 4 — Create GitHub Actions Workflow
Create .github/workflows/deploy.yml:
yamlname: Deploy to HuggingFace Spaces

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          lfs: true

      - name: Push to HuggingFace Space
        env:
          HF_TOKEN: ${{ secrets.TCI_SHIELD_HUGGING_FACE }}
        run: |
          git config --global user.email "deploy@github-actions.com"
          git config --global user.name "GitHub Actions"
          git push https://oauth2:$HF_TOKEN@huggingface.co/spaces/PABPAT/TCI_Shield main --force

Step 5 — Add AWS Secrets to HuggingFace Space

Go to https://huggingface.co/spaces/PABPAT/TCI_Shield
Click Settings → Repository Secrets
Add:

NameValueAWS_ACCESS_KEY_IDyour AWS access keyAWS_SECRET_ACCESS_KEYyour AWS secret keyAWS_DEFAULT_REGIONus-east-1

Click Restart Space


Step 6 — Deploy
Push any change to main branch:
bashgit add .
git commit -m "your message"
git push origin main
GitHub Actions automatically deploys to HuggingFace.

Ongoing Deployment
Every push to main triggers automatic deployment. No manual steps needed.