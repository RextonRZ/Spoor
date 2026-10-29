# Privacy, retention and provider processing

## Data handled

Original videos, working proxies, frame tables, model outputs (SAM boxes/masks, Spark answers), spatial estimates,
case records, agent checkpoints, reports, audit log.

## Controls in the code

- **Authorization before ingest:** every upload records uploader, rights statement, purpose, consent confirmation,
  whether hosted model processing is allowed, and a retention end date. Hosted SAM/Spark calls are refused when
  `hosted_processing_allowed` is false.
- **Standard mode only:** the Meta backend refuses `*-contributor` model IDs. Uploaded clips are sent with a 1-hour
  expiry and deleted after each request.
- **No biometrics:** concept prompts and model outputs that name roles, identity, intent, emotion or protected
  attributes are rejected or filtered (`spoor/safety.py`). People appear only as anonymous per-clip tracks.
- **Access:** bearer tokens, roles `site_admin` / `investigator` / `reviewer`, per-site isolation, rate limit.
- **Media access:** frames are served only through HMAC-signed links that expire after 5 minutes.
- **Audit:** every write (and evidence view) is logged with actor, action and target.
- **Deletion:** `POST /v1/media/{id}/purge` deletes the original, derivatives, observations, tracks and estimates;
  findings that cited them are marked invalid (history kept). `DELETE /v1/cases/{id}` deletes case records.
  Audit entries (IDs only) are retained as the documented exception.
- **Untrusted text:** filenames, captions, imported logs and agent prose are passed to models only as quoted data.

## To verify before real use

Current Meta Model API and Baseten data-retention and training terms (do not rely on "not used for training" as a
full privacy guarantee); legal review of CCTV use at the site; signage/consent; data residency.
