# Mobile category cache

Categories are kept in memory and in device preferences, isolated by API base URL. Opening Browse displays the saved snapshot immediately, even offline. Background revalidation runs on cache access at most once every five minutes per category scope; restarting the repository/app checks saved data again. Changed responses replace the cache for subsequent reads. The screen currently on display is not reset by a background change.

The categories endpoint returns a SHA-256 ETag of its serialized response. The app sends `If-None-Match`; an unchanged response is HTTP 304 with no category body. Clients without ETag support continue receiving the usual JSON list. Category/attribute saves and deletes invalidate the existing server payload cache; its existing maximum lifetime is 30 minutes for changes that bypass signals.

Browse preloads the complete tree with one `include_top=true` request, instead of requesting each parent individually. Once loaded, child navigation filters that snapshot locally. Failed refreshes preserve the last good snapshot; failed first loads can be retried. A schema-versioned storage key avoids mixing old cache formats, so upgrading performs one initial download.

Deploy the API changes and install the updated app. No database migration is required for category caching. The updated app still works with an older server, but that server returns full responses until ETag support is deployed.
