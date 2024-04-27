# The Transcriber
Transcriber &amp; translator for audio files. Like Otter.ai but open-source and almost free.

![Screenshot](screenshot.png)

## Otter.ai

[Otter.ai](https://otter.ai/pricing) monthly subscription is **$16.99**/per user. \
Where you get:
> 1200 monthly transcription minutes; 90 minutes per conversation

## The Transcriber:

**Transcription**:
[Replicate AI models cloud-hosting](https://replicate.com/pricing) with current prices and models used, 1200 minutes will cost approximately **$5.50** \
At least three times cheaper with the same or even better quality of transcription, in my opinion. \
And you pay as you go.

**Translation and summerization**:
[Gemini 1.5 Pro](https://ai.google.dev/pricing) till May 2, 2024 is free. Then TBA.

**Hosting**:
Free tires of [Google Cloud](https://cloud.google.com/free), [Orcale Cloud](https://www.oracle.com/cloud/free/), [AWS](https://aws.amazon.com/free/), [Render](https://render.com/pricing), [Azure](https://azure.microsoft.com/en-us/pricing/free-services), [IBM Cloud](https://www.ibm.com/cloud/free), or low-cost [DigitalOcean](https://www.digitalocean.com/), or any you like.

## Technical details

[Run Whisper model on Replicate](https://replicate.com/openai/whisper) much cheaper than using [OpenAI API for Whisper](https://openai.com/pricing).

I use two models:

[vaibhavs10/incredibly-fast-whisper](https://replicate.com/vaibhavs10/incredibly-fast-whisper) best for speed \
[thomasmol/whisper-diarization](https://replicate.com/thomasmol/whisper-diarization) best for dialogs

Same audio 45 minutes (6 speakers) comparison by model
![Comparison of processing times by model](model-comparison.png)

### Limitations

#### OpenAI Whisper model

[OpenAI Speech to text Whisper model](https://platform.openai.com/docs/guides/speech-to-text)

> File uploads are currently limited to 25 MB.

To avoid this limitation, I use compression. The file size without compression is 63 MB for 45 minutes of audio. However, after compression, the file size reduces to 4 MB for the same duration. Therefore, using compression, we can avoid splitting audio into chunks, and we can increase the limit to approximately 3 hours and 45 minutes of audio without losing transcription quality.

But if you still need to transcript more you can split file using [pydub's](https://github.com/jiaaro/pydub/blob/master/API.markdown) `silence.split_on_silence()` or `silence.detect_silence()` or `silence.detect_nonsilent()`. This function's speed is hardware-dependent, but it is about 10 times faster than listening to the entire file.

In my tests, I face three main problems:
1. These functions are not working as I expect.
2. If split just by time, you can cut in the middle of a word.
3. Post-processing becomes a challenge. It's hard to identify the speaker smoothly. Loss of timestamps.

All this beloongs to very long audio only.

#### Gemini 1.5 Pro

[Gemini 1.5 Pro model name and properties](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models)

> Max output tokens: 8,192 

0.75 words per token = ~6,144 words or about 35 minutes of speaking. But for [non-English languages](https://mor10.com/openai-token-tax/), most words are counted as two or more tokens.

The maximum number of tokens for output is currently 8,192. Audio post-processing, which includes correction and translation, can only be done for files that are approximately 35 minutes long. Other models have a maximum output of 4,096 or less. If you need to process more than 8,192 tokens, you may need to do it in batches, but this will significantly increase the processing time.

Translation by chunks still works, but the quality little bit lower.

> Max audio length: approximately 8.4 hours

It still works well for summarization.

> [2 queries per minute, 1000 queries per day](https://ai.google.dev/gemini-api/docs/models/gemini#model-variations)

[Languages support](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models#language-support) for translation.


### Docs

#### Config secrets

Example of `.env` file:
```
GEMINI_API_KEY = your_api_key
REPLICATE_API_TOKEN = your_api_key
```

You need to replace the path to env_file in `compose.yaml`

[Get Gemini API key](https://ai.google.dev/) \
[Get Replicate API key](https://replicate.com/account/api-tokens)


#### Libraries

[pytube](https://pytube.io/en/latest/)

#### Streamlit

[Develop locally with secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management#develop-locally-with-secrets) \
[Secrets management](https://docs.streamlit.io/develop/concepts/connections/secrets-management)

#### Docker

[Docker Best Practices](https://testdriven.io/blog/docker-best-practices/)

[Docker](https://docs.docker.com/language/python/) \
[Dockerfile reference](https://docs.docker.com/reference/dockerfile/) \
[Dockerfile Linter](https://hadolint.github.io/hadolint/) \
[.dockerignore](https://docs.docker.com/build/building/context/#dockerignore-files)

[Docker Compose](https://docs.docker.com/compose/) \
[Syntax for environment files in Docker Compose](https://docs.docker.com/compose/environment-variables/env-file/) \
[Ways to set environment variables with Compose](https://docs.docker.com/compose/environment-variables/set-environment-variables/) \
[Compose file version 3 reference](https://docs.docker.com/compose/compose-file/compose-file-v3/)

#### GitHub Actions
[Workflow syntax for GitHub Actions](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)

### Deploy

#### Render
[Render Blueprints (IaC)](https://docs.render.com/infrastructure-as-code)
[Deploy from GitHub / GitLab / Bitbucket](https://docs.render.com/web-services#deploy-from-github--gitlab--bitbucket)

#### Google Cloud
[Quickstart: Deploy to Cloud Run](https://cloud.google.com/run/docs/quickstarts/deploy-container) \
[Continuous deployment from Git using Cloud Build](https://cloud.google.com/run/docs/continuous-deployment-with-cloud-build) \
[Tutorial: Deploy your dockerized application on Google Cloud](https://community.intersystems.com/post/tutorial-deploy-your-dockerized-application-google-cloud)

#### Oracle Cloud
[Deploying an Application with Oracle Container Cloud Service](https://www.oracle.com/webfolder/technetwork/tutorials/obe/cloud/container_cloud/deploying_an_app_from_occs/occs-deploy-an-app-obe.html)

#### AWS
[Deploy Docker Containers on Amazon ECS](https://aws.amazon.com/getting-started/hands-on/deploy-docker-containers/)

#### Azure
[Deploy a custom container to Azure App Service with Azure Pipelines](https://learn.microsoft.com/en-us/azure/devops/pipelines/apps/cd/deploy-docker-webapp?view=azure-devops&tabs=python%2Cclassic) \
[Deploy a containerized app to Azure](https://code.visualstudio.com/docs/containers/app-service)

#### Digital Ocean

[How to Deploy from Monorepos](https://docs.digitalocean.com/products/app-platform/how-to/deploy-from-monorepo/) \
[How to Deploy from Container Images](https://docs.digitalocean.com/products/app-platform/how-to/deploy-from-container-images/) \
[How to Use Environment Variables in App Platform](https://docs.digitalocean.com/products/app-platform/how-to/use-environment-variables/#using-bindable-variables-within-environment-variables)