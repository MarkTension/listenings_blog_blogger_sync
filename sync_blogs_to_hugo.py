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
OUTPUT_DIR = Path('listenings_blog/content/archive')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def extract_author(content):
    """Extract author name from content using pattern: ~ Name"""
    # Look for tilde followed by space and name
    match = re.search(r'~\s+([A-Z][a-z]+)', content)
    if match:
        return match.group(1)
    return None


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
    
    frontmatter = f"""+++
date = '{date_str}'
draft = false
title = "{title_escaped}"
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

def save_post_to_file(post):
    """Save a single post as a markdown file"""
    title = post.get('title', 'Untitled')
    filename = sanitize_filename(title) + '.md'
    filepath = OUTPUT_DIR / filename
    
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

def main():
    print("Fetching posts from Blogger...")
    posts = fetch_blogger_posts()
    print(f"Found {len(posts)} posts")
    
    print(f"\nConverting and saving to {OUTPUT_DIR}...")
    for post in posts:
        save_post_to_file(post)
    
    print(f"\n✓ Done! Converted {len(posts)} posts to markdown.")

if __name__ == '__main__':
    main()