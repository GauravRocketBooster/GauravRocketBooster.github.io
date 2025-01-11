import subprocess
import os
from datetime import datetime
from pathlib import Path
import re
import base64
import hashlib
import time

class NotesPublisher:
    def __init__(self, repo_path):
        self.repo_path = Path(repo_path)
        self.posts_dir = self.repo_path / '_posts'
        self.assets_dir = self.repo_path / 'assets' / 'images'
        
        # Create necessary directories
        self.posts_dir.mkdir(exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

    def get_notes_with_images(self):
        """Fetch notes with their images using enhanced AppleScript"""
        print("Fetching notes with images...")
        
        applescript = '''
        tell application "Notes"
            set noteList to {}
            set selectedNotes to notes whose modification date > ((current date) - (7 * days))
            
            repeat with theNote in selectedNotes
                try
                    set noteContent to body of theNote
                    set noteImages to {}
                    
                    -- Get attachments with more detailed logging
                    repeat with theAttachment in attachments of theNote
                        try
                            set attachmentType to type identifier of theAttachment
                            log "Found attachment of type: " & attachmentType
                            
                            if attachmentType starts with "public.image" or attachmentType starts with "com.apple.quicktime-image" then
                                set imageFile to path of theAttachment
                                if imageFile is not missing value then
                                    log "Found image path: " & imageFile
                                    set end of noteImages to imageFile
                                end if
                            end if
                        end try
                    end repeat
                    
                    -- Log the data we're about to return
                    log "Note title: " & name of theNote
                    log "Number of images found: " & (count of noteImages)
                    
                    set noteData to {|title|:name of theNote, content:noteContent, images:noteImages}
                    copy noteData to end of noteList
                end try
            end repeat
            
            return noteList
        end tell
        '''
        
        try:
            print("Executing AppleScript...")
            result = subprocess.run(['osascript', '-e', applescript], 
                                 capture_output=True, 
                                 text=True,
                                 timeout=60)
            
            if result.returncode != 0:
                print(f"Error: {result.stderr}")
                return []
            
            # Parse the complex output
            notes = []
            current_note = {}
            
            # Split by note boundaries
            raw_notes = result.stdout.strip().split('title:')
            
            for raw_note in raw_notes[1:]:  # Skip first empty split
                try:
                    # Extract title
                    title_end = raw_note.find('content:')
                    title = raw_note[:title_end].strip()
                    
                    # Extract content
                    content_start = title_end + 8  # len('content:')
                    content_end = raw_note.find('images:')
                    content = raw_note[content_start:content_end].strip()
                    
                    # Extract image paths
                    images_str = raw_note[content_end + 7:].strip()
                    images = [img.strip() for img in images_str.split(',') if img.strip()]
                    
                    notes.append({
                        'title': title,
                        'content': content,
                        'images': images,
                        'modified_date': datetime.now()
                    })
                except Exception as e:
                    print(f"Error processing note: {str(e)}")
                    continue
            
            print(f"Found {len(notes)} notes with content")
            return notes
            
        except subprocess.TimeoutExpired:
            print("Timeout while fetching notes. Please try again.")
            return []
        except Exception as e:
            print(f"Error: {str(e)}")
            return []

    def copy_image_to_assets(self, image_path):
        """Copy image to assets directory and return new path"""
        try:
            print(f"Attempting to copy image: {image_path}")
            
            # Handle potential file:// prefix in image paths
            if image_path.startswith("file://"):
                image_path = image_path[7:]
            
            if not image_path or not os.path.exists(image_path):
                print(f"Image path does not exist: {image_path}")
                return None
            
            # Print file details for debugging
            file_stat = os.stat(image_path)
            print(f"File size: {file_stat.st_size} bytes")
            print(f"File permissions: {oct(file_stat.st_mode)}")
            
            # Generate unique filename based on content and timestamp
            with open(image_path, 'rb') as f:
                content = f.read()
                file_hash = hashlib.md5(content + str(time.time()).encode()).hexdigest()[:10]
            
            # Keep original extension or default to .png
            extension = os.path.splitext(image_path)[1].lower() or '.png'
            new_filename = f"{file_hash}{extension}"
            new_path = self.assets_dir / new_filename
            
            # Copy file with debug output
            print(f"Copying image from {image_path} to {new_path}")
            
            # Try both cp command and native Python copy
            try:
                subprocess.run(['cp', image_path, str(new_path)], 
                             check=True, 
                             capture_output=True, 
                             text=True)
            except subprocess.CalledProcessError as e:
                print(f"cp command failed: {e.stderr}")
                # Fallback to Python's native file copy
                import shutil
                shutil.copy2(image_path, new_path)
            
            if new_path.exists():
                print(f"Successfully copied image to {new_path}")
                # Verify the copied file
                if new_path.stat().st_size > 0:
                    return f"/assets/images/{new_filename}"
                else:
                    print("Warning: Copied file is empty")
                    return None
            else:
                print(f"Failed to copy image to {new_path}")
                return None
            
        except Exception as e:
            print(f"Error processing image {image_path}: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None

    def process_content(self, content, images):
        """Process note content to proper markdown format"""
        # Extract hashtags
        tags = re.findall(r'#(\w+)', content)
        
        # Remove standalone hashtags but keep them in text
        content = re.sub(r'\s#(\w+)(?=\s|$)', r' \1', content)
        
        # Convert Apple Notes formatting to markdown
        # Replace bullet points
        content = re.sub(r'•\s', '* ', content)
        
        # Replace numbered lists
        content = re.sub(r'^\d+\.\s', '1. ', content, flags=re.MULTILINE)
        
        # Replace checkboxes
        content = re.sub(r'☐', '- [ ]', content)
        content = re.sub(r'☑', '- [x]', content)
        
        # Handle basic formatting
        content = re.sub(r'_(.+?)_', r'*\1*', content)  # italics
        content = re.sub(r'\*(.+?)\*', r'**\1**', content)  # bold
        
        # Process images
        processed_images = []
        for img_path in images:
            new_path = self.copy_image_to_assets(img_path)
            if new_path:
                processed_images.append(f"![Image]({new_path})")
        
        # Add processed images to content
        if processed_images:
            content += "\n\n" + "\n\n".join(processed_images)
        
        return content, tags

    def create_markdown_post(self, note):
        """Convert note to Jekyll-compatible markdown"""
        print(f"Processing note: {note['title']}")
        
        # Process content and extract tags
        processed_content, tags = self.process_content(note['content'], note.get('images', []))
        
        # Create slug from title
        slug = re.sub(r'[^a-zA-Z0-9-]', '-', note['title'].lower())
        slug = re.sub(r'-+', '-', slug).strip('-')
        
        date_str = note['modified_date'].strftime('%Y-%m-%d')
        filename = f"{date_str}-{slug}.md"
        
        # Create front matter
        front_matter = f"""---
layout: post
title: "{note['title']}"
date: {note['modified_date'].strftime('%Y-%m-%d %H:%M:%S')}
tags: [{', '.join(tags)}]
---

{processed_content}
"""
        
        file_path = self.posts_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(front_matter)
        
        print(f"Created post: {filename}")
        return filename

    def publish_notes(self):
        """Publish notes to GitHub Pages repository"""
        notes = self.get_notes_with_images()
        
        if not notes:
            print("No recent notes found to publish")
            return
        
        # Add debug logging
        print(f"Found {len(notes)} notes to process")
        for note in notes:
            print(f"Note title: {note.get('title')}")
            print(f"Note content length: {len(note.get('content', ''))}")
            print(f"Note images: {len(note.get('images', []))}")
        
        published_files = []
        for note in notes:
            if not note.get('title') or not note.get('content'):
                continue
            
            filename = self.create_markdown_post(note)
            published_files.append(filename)
            # Add debug logging
            print(f"Created file: {filename}")
        
        if published_files:
            print("\nCommitting changes to GitHub...")
            os.chdir(self.repo_path)
            subprocess.run(['git', 'add', '.'])
            subprocess.run(['git', 'commit', '-m', 
                          f"Update notes {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
            subprocess.run(['git', 'push'])
            print(f"\nSuccessfully published {len(published_files)} notes!")
        else:
            print("No notes were published")

if __name__ == "__main__":
    publisher = NotesPublisher(
        repo_path="/Users/gauravjeetsingh/Desktop/thinkingjet.github.io"
    )
    publisher.publish_notes()