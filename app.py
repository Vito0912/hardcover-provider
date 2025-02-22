# file: app.py
import os
import time
import json
import logging
from typing import Optional

from fake_useragent import UserAgent
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.params import Path
from fastapi.security import APIKeyHeader
import requests

from models import BookMetadata, SearchResponse, SeriesMetadata
from caching import (
    get_cache_key, get_from_memory, get_from_file, store_in_memory
)
from rate_limit import rate_limit_check, clear_old_ips
from retreive_api_keys import ApiKeys

logger = logging.getLogger("uvicorn")
logging.basicConfig(level=logging.INFO)

api_key_header = APIKeyHeader(name="AUTHORIZATION", auto_error=False)
key = ApiKeys()

def get_api_key(api_key: str = Depends(api_key_header)):
    if not api_key:
        raise HTTPException(
            status_code=401, detail="Unauthorized: Missing or invalid Api Key"
        )
    return api_key


def search_for_books(query: str, author: Optional[str], lang: Optional[str], type: Optional[str]) -> list[BookMetadata]:
    url = "	https://search.hardcover.app/multi_search?x-typesense-api-key=cf0jYiqkIXNYh2EnJr1RqHIYJbKOGoGk"
    headers = {
        'User-Agent': UserAgent().random,
        'Content-Type': 'application/json'
    }
    graphql_query = '{"searches":[{"per_page":30,"prioritize_exact_match":true,"num_typos":5,"query_by":"title,isbns,series_names,author_names,alternative_titles","sort_by":"users_count:desc,_text_match:desc","query_by_weights":"5,5,3,2,1","collection":"Book_production","q":"[[1]]","page":1}]}'

    graphql_query = graphql_query.replace("[[1]]", query)

    response = requests.post(url, headers=headers, json=json.loads(graphql_query))

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Error calling Hardcover API: {e}")
        logger.error(f"Response: {response.text}")
        raise HTTPException(
            status_code=500,
            detail="Error calling external API"
        )
    all_data = response.json()

    data = {"data": all_data}
    data["data"]["results"] = all_data["results"][0]

    # Ensure author is a valid non-empty string
    if author and isinstance(author, str) and author.strip():
        author_parts = [part.lower() for part in author.split()]
    else:
        author_parts = []

    matches = []

    def name_matches(name, parts):
        """
        Check if a name matches any part of the given name parts.
        Returns the number of parts that match.
        """
        name_parts = name.lower().split()
        return sum(int(part in name_parts) for part in parts)

    for book in data["data"]["results"]["hits"]:
        scores = []

        if author_parts:
            author_names = book["document"].get("author_names", [])

            # Calculate match score for each author name
            scores = [name_matches(name, author_parts) for name in author_names]

            if not any(scores):
                continue

        # Store the book along with its highest match score, default to 0 if no author provided
        matches.append({
            "score": max(scores) if scores else 0,
            "metadata": {
                "id": book["document"]["id"],
                "title": book["document"]["title"],
                "author": ', '.join(book["document"].get("author_names", [])),
            },
        })

    # Sort the matches, putting those with higher match scores first
    matches.sort(key=lambda x: x["score"], reverse=True)

    # Extract the sorted BookMetadata objects
    matches = [match["metadata"] for match in matches]

    headers['Authorization'] = f'Bearer {key.get_key().key}'
    headers['User-Agent'] = UserAgent().random

    ids = [match["id"] for match in matches]
    ids = set(ids)

    payload = "{\n  \"query\": \"query FindEditionsForBook($bookId: [Int!]!, $limit: Int!, $offset: Int!, $formats: [Int!]!, $userId: Int, $includeCurrentUser: Boolean!) {\\n  books(\\n    where: {\\n      id: { _in: $bookId }\\n    }\\n    limit: 10\\n    order_by: { users_count: desc }\\n  ) {\\n    title\\n    description\\n    id\\n    contributions {\\n      author {\\n        name\\n      }\\n    }\\n\\t\\ttaggings {\\n      tag {\\n        tag\\n      }\\n    }\\n\\t\\tbook_series {\\n      position\\n\\t\\t\\tseries {\\n\\t\\t\\t\\tname\\n\\t\\t\\t}\\n    }\\n    editions(\\n      where: { book_id: { _in: $bookId }, reading_format_id: { _in: $formats }[[2]]}\\n      order_by: { users_count: desc }\\n      limit: $limit\\n      offset: $offset\\n    ) {\\n    ...EditionFragment\\n    list_books(where: {list: {user_id: {_eq: $userId}, slug: {_eq: \\\"owned\\\"}}}) @include(if: $includeCurrentUser) {\\n      ...ListBookFragment\\n      __typename\\n    }\\n    __typename\\n    }\\n  }\\n}\\n\\nfragment EditionFragment on editions {\\n  id\\n  title\\n\\tpages\\n  asin\\n  isbn13: isbn_13\\n  releaseYear: release_year\\n  pages\\n\\tdescription\\n  audioSeconds: audio_seconds\\n  cachedImage: cached_image\\n  editionFormat: edition_format\\n  language {\\n    language\\n code2 \\n }\\n  readingFormat: reading_format {\\n    format\\n  }\\n  country {\\n    name\\n  }\\n\\tcontributions {\\n\\t\\tauthor {\\n\\t\\t\\tname\\n\\t\\t}\\n\\t}\\n  publisher {\\n    ...PublisherFragment\\n  }\\n}\\n\\nfragment ListBookFragment on list_books {\\n  id\\n  position\\n}\\n\\nfragment PublisherFragment on publishers {\\n  id\\n  name\\n}\\n\",\n  \"operationName\": \"FindEditionsForBook\",\n  \"variables\": {\n    \"bookId\": [[0]],\n    \"formats\": [[1]],\n    \"limit\": 25,\n    \"offset\": 0,\n    \"userId\": 0,\n    \"includeCurrentUser\": false\n  }\n}"

    if lang is not None and len(lang) == 2:
        payload = payload.replace("[[2]]", f", language: {{ code2: {{ _eq: \\\"{lang}\\\" }} }}")
    else:
        payload = payload.replace("[[2]]", "")

    if (lang is not None and len(lang) > 2 and lang == "book") or type == "book":
        payload = payload.replace("[[1]]", "[1,4]")
    elif (lang is not None and len(lang) > 2 and lang == "abook") or type == "abook":
        payload = payload.replace("[[1]]", "[2,3]")
    else:
        payload = payload.replace("[[1]]", "[1,2,3,4]")

    if len(ids) == 0:
        raise HTTPException(
            status_code=404,
            detail="No books found"
        )
    else:
        payload = payload.replace("[[0]]", str(ids).replace("'", "").replace('{', '[').replace('}', ']'))

    url = "https://api.hardcover.app/v1/graphql"

    response = requests.post(url, headers=headers, data=payload)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Error calling Hardcover API: {e}")
        logger.error(f"Payload: {payload}")
        logger.error(f"Response: {response.text}")
        raise HTTPException(
            status_code=500,
            detail="Error calling external API"
        )

    data = response.json()

    matches = []
    try:
        for book in data["data"]["books"]:
            for edition in book.get("editions", {}):

                series_list = edition.get("book_series", [])
                authors_edition = [contribution["author"]["name"]
                                   for contribution in edition.get("contributions", [])
                                   if "author" in contribution and "name" in contribution["author"]]
                authors_book = None
                if not authors_edition:
                    authors_book = [contribution["author"]["name"]
                                    for contribution in book.get("contributions", [])
                                    if "author" in contribution and "name" in contribution["author"]]

                author = ", ".join(authors_edition) if authors_edition else ", ".join(authors_book)

                matches.append(BookMetadata(
                    title=edition.get("title") or book.get("title"),
                    subtitle=edition.get("subtitle"),
                    author=author,
                    publisher=edition.get("publisher", {}).get("name") if edition.get("publisher") else None,
                    publishedYear=edition.get("releaseYear"),
                    description=edition.get("description") or book.get("description"),
                    cover=edition.get("cachedImage", {}).get("url") if edition.get("cachedImage") else None,
                    isbn=edition.get("isbn13"),
                    asin=edition.get("asin"),
                    tags=[tag["tag"]["tag"] for tag in edition.get("taggings", []) if tag.get("tag")],
                    series=[SeriesMetadata(series=series["series"]["name"], sequence=series["position"]) for series in
                            series_list] if series_list else [],
                    language=edition.get("language", {}).get("language") if edition.get("language") else None,
                    duration=int(str(edition.get("audioSeconds"))) / 60 if edition.get("audioSeconds") else None
                ))
    except Exception as e:
        logger.error(f"Error parsing response: {e}")
        logger.error(f"Response: {data}")
        raise HTTPException(
            status_code=500,
            detail="Error parsing response"
        )

    return matches


def create_app() -> FastAPI:
    app = FastAPI(
        openapi_url="/openapi.json",
        servers=[{"url": "https://provider.vito0912.de/hardcover"}],
        title="Custom Metadata Provider",
        version="0.1.0"
    )

    def search(
            request: Request,
            query: str = Query(..., description="Book to search for"),
            author: Optional[str] = Query(None, description="Author name"),
            lang_code: Optional[str] = None,
            content_type: Optional[str] = None,
            api_key: str = Depends(get_api_key),
    ):
        if lang_code not in ["book", "abook", None] and len(lang_code) != 2:
            raise HTTPException(
                status_code=400,
                detail="Invalid language code or content type. Must be a 2-letter language code or one of book, abook, None."
            )

        if content_type not in ["book", "abook", None]:
            raise HTTPException(
                status_code=400,
                detail="Invalid content type. Must be one of: book, abook, None"
            )

        if len(query) < 3:
            raise HTTPException(
                status_code=400,
                detail="Query must be at least 3 characters long"
            )

        # Log IP and user agent
        ip_address = request.headers.get("X-Forwarded-For", request.client.host)
        user_agent = request.headers.get("User-Agent", "Unknown")
        search_str = f"query={query}, author={author or ''}"

        # Time in format YYYY-MM-DD HH:MM:SS
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        logger.info(f"{timestamp} - Request from IP: {ip_address}, Agent: {user_agent}, Search: {search_str}")

        # Check cache
        cache_key = get_cache_key(query, author or "", lang_code, content_type)
        response_bytes = get_from_memory(cache_key)
        if not response_bytes:
            response_bytes = get_from_file(cache_key)
        if response_bytes:
            # Cache HIT - do not count towards rate limit
            logger.info("Cache hit for request.")
            content_dict = json.loads(response_bytes.decode("utf-8"))
            return SearchResponse(**content_dict)

        # Cache MISS => rate limit check
        rate_limit_check(ip_address)

        # Actual search
        logger.info("Cache miss - calling search_for_books")
        matches = search_for_books(query, author, lang_code, content_type)
        response_obj = SearchResponse(matches=matches)
        response_bytes = json.dumps(response_obj.model_dump()).encode("utf-8")

        # Store in memory
        store_in_memory(cache_key, response_bytes)

        return response_obj

    @app.get(
        "/{lang_code:path}/{content_type:path}/search",
        summary="Search for books",
        description="Search for books",
        response_model=SearchResponse,
        responses={
            200: {
                "description": "OK"
            },
            400: {"description": "Bad Request"},
            401: {"description": "Unauthorized"},
            500: {"description": "Internal Server Error"}
        },
        tags=["search"],
    )
    def search_endpoint(
            request: Request,
            query: str = Query(..., description="Book to search for"),
            author: Optional[str] = Query(None, description="Author name"),
            lang_code: Optional[str] = Path(description="Language code"),
            content_type: Optional[str] = Path(description="Content type: book|abook|None"),
            api_key: str = Depends(get_api_key),
    ) -> SearchResponse:
        return search(request, query=query, author=author, lang_code=lang_code, content_type=content_type,
                      api_key=api_key)

    @app.get(
        "/{lang_code:path}/search",
        summary="Search for books",
        description="Search for books",
        response_model=SearchResponse,
        responses={
            200: {
                "description": "OK"
            },
            400: {"description": "Bad Request"},
            401: {"description": "Unauthorized"},
            500: {"description": "Internal Server Error"}
        },
        tags=["search"],
    )
    def search_endpoint_lang_only(
            request: Request,
            query: str = Query(..., description="Book to search for"),
            author: Optional[str] = Query(None, description="Author name"),
            lang_code: Optional[str] = Path(description="Language code"),
            api_key: str = Depends(get_api_key),
    ) -> SearchResponse:
        return search(request, query=query, author=author, lang_code=lang_code, api_key=api_key)

    @app.get(
        "/search",
        summary="Search for books",
        description="Search for books",
        response_model=SearchResponse,
        responses={
            200: {
                "description": "OK"
            },
            400: {"description": "Bad Request"},
            401: {"description": "Unauthorized"},
            500: {"description": "Internal Server Error"}
        },
        tags=["search"],
    )
    def search_endpoint_no_params(
            request: Request,
            query: str = Query(..., description="Book to search for"),
            author: Optional[str] = Query(None, description="Author name"),
            api_key: str = Depends(get_api_key),
    ) -> SearchResponse:
        return search(request, query=query, author=author, api_key=api_key)

    return app
