# Hardcover Metadata Provider for ABS

This repository provides a service instance for the Hardcover API to use as a metadata Provider for ABS. Although the rate limit can be expanded easily, it is currently capped for the reasons outlined in this README. If you use this provider normally you should never hit it.

> [!IMPORTANT]
> This instance is **not** affiliated with Hardcover.

## Overview

This provider offers all data available for a specific book from Hardcover. No account is required, and therefore no user agreements are necessary.

> [!WARNING]
>
> If you self-host this instance, please avoid overusing it. The service is community-driven and maintained by many contributors. Occasionally, the service may be slow, so refrain from extensive stress tests—especially, do not perform a quick match of your entire library—as this could harm the service.

## Using Hardcover

> [!IMPORTANT]
>
> I am not affiliated with Hardcover, nor was I ever asked to advertise it. However, I believe it is important to show you what you are using so that you might consider supporting it.

> [!NOTE]
>
> If you cannot find a book (especially audiobooks), consider creating an account on Hardcover and adding the missing title. This benefits everyone by supporting the service and enhancing its data.

Key features of Hardcover include:

- Free access to all major functions.
- Import of most books using an ISBN.
- A robust AI that powers search and recommendations.
- Much more.

If you appreciate the service, please consider showing your support to help it grow (Support Plan) — think of it as a more user-friendly alternative to platforms like GoodReads.

## Service Endpoint

The instance is available at the following URL (use `abs` as the Auth-Value for all requests):

```
https://provider.vito0912.de/hardcover
```

### URL Options

You can customize requests further using the following URL structure:

```
https://provider.vito0912.de/hardcover/<language>/<type>
```

- **Language Filtering:**  
  Replace `<language>` with the 2-digit language code to filter results exclusively by that language. This is recommended because English titles are often returned by default, even if books in other languages are available.  
  **Example:** For English books, use `en`.

- **Type Filtering:**  
  Replace `<type>` with one of the following options:
  - `book` – to include only books.
  - `abook` – to include only audiobooks.

**Example URL for English Books:**

```
https://provider.vito0912.de/hardcover/en/book
```

**Example URL for Audiobooks in any language:**

```
https://provider.vito0912.de/hardcover/abook
```

*Ensure that if you do not wish to apply filtering, the URL does not end with a trailing slash.*

## Disclaimer

> [!NOTE]
>
> I am not affiliated with Hardcover.
