# API Reference

## POST /api/artifacts

Starts a new scrape or requests the next page of data.

**New download:**

```json
{
  "case_id": "123",
  "identifier": "mothershipsg",
  "description": "Instagram Profile of Mothership"
}
```

**Pagination:**

```json
{
  "case_id": "123",
  "artifact_id": "XXX",
  "content_type": "post"
}
```

`content_type` must be `"post"` or `"reel"`.

**Response** (`202 Accepted`):

```json
{
  "artifact_id": "XXX"
}
```

If the identifier is already being processed, returns `200` with the existing `artifact_id`.

---

## GET /api/artifacts

Lists all artifacts.

**Response** (`200 OK`):

```json
[
  {
    "status": "success",
    "has_more_data": [
      { "content_type": "post", "has_more_data": true },
      { "content_type": "reel", "has_more_data": true }
    ],
    "metadata": {
      "platform": "instagram",
      "identifier": "mothershipsg",
      "display_name": "Mothership",
      "profile_pic": "http://<image_url>",
      "description": "Instagram Profile of Mothership"
    },
    "contents": [
      {
        "error_message": "",
        "owners": ["mothershipsg"],
        "caption": "XXX",
        "datetime": "2024-01-01T12:12:12Z",
        "content_type": "post",
        "media_content": [
          {
            "media_type": "image",
            "original_url": "http://<image_url>",
            "url": "/api/blob/<blob_id>"
          },
          {
            "media_type": "video",
            "original_url": "http://<video_url>",
            "original_thumbnail_url": "http://<thumbnail_url>",
            "url": "/api/blob/<blob_id>",
            "thumbnail_url": "/api/blob/<blob_id>"
          }
        ]
      },
      {
        "error_message": "",
        "owners": ["mothershipsg"],
        "caption": "XXX",
        "datetime": "2024-02-01T12:12:12Z",
        "content_type": "reel",
        "media_content": [
          {
            "media_type": "video",
            "original_url": "http://<video_url>",
            "original_thumbnail_url": "http://<thumbnail_url>",
            "url": "/api/blob/<blob_id>",
            "thumbnail_url": "/api/blob/<blob_id>"
          }
        ]
      }
    ]
  },
  {
    "status": "processing",
    "metadata": {
      "platform": "instagram",
      "identifier": "mothershipsg",
      "description": "Instagram Profile of Mothership"
    },
    "contents": []
  }
]
```

> While an artifact is `"processing"` or `"downloading"`, `contents` is empty and `metadata` only contains `platform`, `identifier`, and `description`. Once `status` is `"success"`, the full profile info and contents are included.

---

## GET /api/artifacts/{id}

Returns a single artifact by ID.

**Response** (`200 OK`):

```json
{
  "status": "success",
  "has_more_data": [
    { "content_type": "post", "has_more_data": true },
    { "content_type": "reel", "has_more_data": true }
  ],
  "metadata": {
    "platform": "instagram",
    "identifier": "mothershipsg",
    "display_name": "Mothership",
    "profile_pic": "http://<image_url>",
    "description": "Instagram Profile of Mothership"
  },
  "contents": [
    {
      "error_message": "",
      "owners": ["mothershipsg"],
      "caption": "XXX",
      "datetime": "2024-01-01T12:12:12Z",
      "content_type": "post",
      "media_content": [
        {
          "media_type": "image",
          "original_url": "http://<image_url>",
          "url": "/api/blob/<blob_id>"
        },
        {
          "media_type": "video",
          "original_url": "http://<video_url>",
          "original_thumbnail_url": "http://<thumbnail_url>",
          "url": "/api/blob/<blob_id>",
          "thumbnail_url": "/api/blob/<blob_id>"
        }
      ]
    },
    {
      "error_message": "",
      "owners": ["mothershipsg"],
      "caption": "XXX",
      "datetime": "2024-02-01T12:12:12Z",
      "content_type": "reel",
      "media_content": [
        {
          "media_type": "video",
          "original_url": "http://<video_url>",
          "original_thumbnail_url": "http://<thumbnail_url>",
          "url": "/api/blob/<blob_id>",
          "thumbnail_url": "/api/blob/<blob_id>"
        }
      ]
    }
  ]
}
```

Returns `404` if the artifact does not exist.

---

## GET /api/blob/{blob_id}

Serves a downloaded media file (image or video) directly.

Returns the binary file with the appropriate `Content-Type` header (e.g. `image/jpeg`, `video/mp4`). Returns `404` if the blob does not exist.

---

## GET /api/health

Health check endpoint.

**Response** (`200 OK`):

```json
{
  "message": "success"
}
```
