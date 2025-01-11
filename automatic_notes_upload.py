import subprocess
import os
from datetime import datetime
from pathlib import Path

class NotesPublisher:
    def __init__(self, repo_path):
        self.repo_path = Path(repo_path)
        self.posts_dir = self.repo_path / '_posts'
        self.posts_dir.mkdir(exist_ok=True)

    def get_recent_notes(self):
        """Fetch only recent notes using AppleScript"""
        print("Fetching recent notes...")
        
        applescript = '''
        tell application "Notes"
            -- Get only notes from the last week
            set myNotes to {}
            set selectedNotes to notes whose modification date > (current date) - 7 * days
            repeat with theNote in selectedNotes
                set noteData to {name:name of theNote, body:body of theNote}
                copy noteData to end of myNotes
            end repeat
            return myNotes
        end tell
        '''
        
        try:
            print("Executing AppleScript...")
            result = subprocess.run(['osascript', '-e', applescript], 
                                 capture_output=True, 
                                 text=True,
                                 timeout=30)  # Add timeout
            
            if result.returncode != 0:
                print(f"Error: {result.stderr}")
                return []
            
            # Parse the output
            notes = []
            current_note = {}
            
            for line in result.stdout.strip().split(', '):
                if line.startswith('name:'):
                    if current_note:
                        notes.append(current_note)
                    current_note = {'title': line[5:].strip()}
                elif line.startswith('body:'):
                    current_note['content'] = line[5:].strip()
                    current_note['modified_date'] = datetime.now()
            
            if current_note:
                notes.append(current_note)
            
            print(f"Found {len(notes)} recent notes")
            return notes
            
        except subprocess.TimeoutExpired:
            print("Timeout while fetching notes. Please try again.")
            return []
        except Exception as e:
            print(f"Error: {str(e)}")
            return []

    def publish_notes(self):
        """Publish notes to GitHub Pages repository"""
        notes = self.get_recent_notes()
        
        if not notes:
            print("No recent notes found to publish")
            return
        
        print("Converting notes to markdown...")
        for note in notes:
            if not note.get('title') or not note.get('content'):
                continue
                
            date_str = datetime.now().strftime('%Y-%m-%d')
            filename = f"{date_str}-{note['title'].lower().replace(' ', '-')}.md"
            file_path = self.posts_dir / filename
            
            # Create front matter
            content = f"""---
layout: post
title: "{note['title']}"
date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
categories: notes
---

{note['content']}
"""
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Created post: {filename}")
        
        print("Committing changes to GitHub...")
        os.chdir(self.repo_path)
        subprocess.run(['git', 'add', '.'])
        subprocess.run(['git', 'commit', '-m', f"Update notes {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
        subprocess.run(['git', 'push'])
        print("Done!")

if __name__ == "__main__":
    publisher = NotesPublisher(
        repo_path="/Users/gauravjeetsingh/Desktop/thinkingjet.github.io"
    )
    publisher.publish_notes()