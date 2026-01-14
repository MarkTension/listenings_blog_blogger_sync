import os
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from googleapiclient.discovery import build
import html2text

# Load environment variables
load_dotenv()

# Get API credentials from .env
API_KEY = os.getenv('BLOGGER_API_KEY')
BLOG_ID = os.getenv('BLOGGER_BLOG_ID')

# Configuration
OUTPUT_DIR = Path('listenings_blog/content/posts')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def extract_author(content):
    """Extract author name from content using pattern: ~Name or ~ Name"""
    # Look for tilde followed by optional space and a single word (name)
    match = re.search(r'~\s*([A-Z][a-z]+)', content)
    if match:
        return match.group(1)
    return None


def extract_album_info(title):
    """
    Extract artist, album, and year from title.
    Expected formats:
    - "Artist - Album"
    - "Artist - Album (Year)"
    - "Artist – Album"
    - "Artist – Album (Year)"
    """
    # Try to extract year in parentheses at the end
    year_match = re.search(r'\((\d{4})\)\s*$', title)
    year = year_match.group(1) if year_match else None
    
    # Remove year from title for further processing
    title_without_year = re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip()
    
    # Split by dash (either - or –)
    parts = re.split(r'\s*[–-]\s*', title_without_year, maxsplit=1)
    
    if len(parts) == 2:
        artist = parts[0].strip()
        album = parts[1].strip()
        return artist, album, year
    
    # If no clear split, return None values
    return None, None, year


def create_description(title, author):
    """
    Create a description in the format:
    [Artist] - [Album] ([Year]): An album recommendation by [Author] on why to listen to this album back-to-back.
    """
    artist, album, year = extract_album_info(title)
    
    if not artist or not album:
        # Fallback if we can't parse the title
        if author:
            return f"An album recommendation by {author} on why to listen to this album back-to-back."
        else:
            return "An album recommendation on why to listen to this album back-to-back."
    
    # Build description
    if year:
        desc = f"{artist} - {album} ({year}): An album recommendation"
    else:
        desc = f"{artist} - {album}: An album recommendation"
    
    if author:
        desc += f" by {author}"
    
    desc += " on why to listen to this album back-to-back."
    
    return desc


def sanitize_filename(title):
    """Convert title to a safe filename"""
    # Convert to lowercase and replace spaces with hyphens
    filename = title.lower()
    # Remove special characters except hyphens and underscores
    filename = re.sub(r'[^\w\s-]', '', filename)
    # Replace spaces and multiple hyphens with single hyphen
    filename = re.sub(r'[-\s]+', '-', filename)
    # Remove leading/trailing hyphens
    filename = filename.strip('-')
    return filename

def html_to_markdown(html_content):
    """Convert HTML to Markdown"""
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.ignore_emphasis = False
    h.body_width = 0  # Don't wrap lines
    return h.handle(html_content).strip()

def create_frontmatter(post, author=None):
    """Create Hugo frontmatter for a post"""
    title = post.get('title', 'Untitled')
    # Parse the published date
    published = post.get('published', '')
    date_obj = datetime.fromisoformat(published.replace('Z', '+00:00'))
    date_str = date_obj.strftime('%Y-%m-%dT%H:%M:%S%z')
    # Format timezone with colon (e.g., +01:00)
    date_str = date_str[:-2] + ':' + date_str[-2:]
    
    # Get labels (tags)
    labels = post.get('labels', [])
    
    # Escape double quotes and backslashes in title for TOML
    title_escaped = title.replace('\\', '\\\\').replace('"', '\\"')
    
    # Create description
    description = create_description(title, author)
    description_escaped = description.replace('\\', '\\\\').replace('"', '\\"')
    
    frontmatter = f"""+++
date = '{date_str}'
draft = false
title = "{title_escaped}"
description = "{description_escaped}"
"""
    
    if author:
        frontmatter += f"\nauthor = '{author}'"
    
    if labels:
        frontmatter += f"\ntags = {labels}"
    
    frontmatter += "\n+++"
    
    return frontmatter

def fetch_blogger_posts():
    """Fetch all posts from Blogger"""
    if not API_KEY or not BLOG_ID:
        raise ValueError("Missing BLOGGER_API_KEY or BLOGGER_BLOG_ID in .env file")
    
    service = build('blogger', 'v3', developerKey=API_KEY)
    
    posts = []
    page_token = None
    
    while True:
        # Fetch posts
        request = service.posts().list(
            blogId=BLOG_ID,
            maxResults=500,
            pageToken=page_token,
            fetchImages=True,
            status='LIVE'  # Only fetch published posts
        )
        response = request.execute()
        
        if 'items' in response:
            posts.extend(response['items'])
        
        # Check if there are more pages
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    
    return posts

def save_post_to_file(post, overwrite=False):
    """Save a single post as a markdown file"""
    title = post.get('title', 'Untitled')
    filename = sanitize_filename(title) + '.md'
    filepath = OUTPUT_DIR / filename
    
    # Check if file exists and overwrite is False
    if filepath.exists() and not overwrite:
        print(f"⊘ Skipped: {filename} (already exists)")
        return None
    
    # Get content
    html_content = post.get('content', '')
    markdown_content = html_to_markdown(html_content)
    
    # Extract author from content
    author = extract_author(markdown_content)
    
    # Create frontmatter
    frontmatter = create_frontmatter(post, author)
    
    # Combine and save
    full_content = f"{frontmatter}\n\n{markdown_content}\n"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    print(f"✓ Saved: {filename}")
    return filepath

def main(overwrite=False):
    print("Fetching posts from Blogger...")
    posts = fetch_blogger_posts()
    print(f"Found {len(posts)} posts")
    
    print(f"\nConverting and saving to {OUTPUT_DIR}...")
    saved_count = 0
    skipped_count = 0
    
    for post in posts:
        result = save_post_to_file(post, overwrite=overwrite)
        if result:
            saved_count += 1
        else:
            skipped_count += 1
    
    print(f"\n✓ Done! Saved {saved_count} posts, skipped {skipped_count} existing posts.")

if __name__ == '__main__':
    # Set overwrite=True to overwrite existing files
    main(overwrite=True)