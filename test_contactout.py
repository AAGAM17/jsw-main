import os
import requests
from dotenv import load_dotenv
import json

def test_contactout_api():
    """Test ContactOut API with a LinkedIn profile URL."""
    load_dotenv()
    
    # Get API token from environment variable
    api_token = os.getenv('CONTACTOUT_TOKEN')
    if not api_token:
        print("Error: CONTACTOUT_TOKEN not found in environment variables")
        return
    
    # LinkedIn profile URL to test
    linkedin_url = "https://in.linkedin.com/in/harshchaudharisigma7"
    
    # ContactOut API endpoint
    api_url = "https://api.contactout.com/v1/people/linkedin"
    
    # Request headers
    headers = {
        "authorization": "basic",
        "token": api_token
    }
    
    # Query parameters
    params = {
        "profile": linkedin_url,
        "include_phone": "true"
    }
    
    try:
        # Make API request
        print("\nMaking request with:")
        print(f"URL: {api_url}")
        print(f"Headers: {json.dumps(headers, indent=2)}")
        print(f"Params: {json.dumps(params, indent=2)}")
        
        response = requests.get(api_url, headers=headers, params=params)
        
        # Print status code and URL
        print(f"\nStatus Code: {response.status_code}")
        print(f"Request URL: {response.url}")
        
        # Check if request was successful
        if response.status_code == 200:
            # Parse and print the response data
            data = response.json()
            print("\nAPI Response:")
            print(json.dumps(data, indent=2))
            
            # Extract and display key information
            if 'profile' in data:
                profile = data['profile']
                print("\nExtracted Information:")
                print(f"LinkedIn URL: {profile.get('url', 'N/A')}")
                
                # Display work emails
                work_emails = profile.get('work_email', [])
                if work_emails:
                    print("\nWork Emails found:")
                    for email in work_emails:
                        status = profile.get('work_email_status', {}).get(email, 'Unknown')
                        print(f"- {email} (Status: {status})")
                else:
                    print("\nNo work emails found")
                
                # Display personal emails
                personal_emails = profile.get('personal_email', [])
                if personal_emails:
                    print("\nPersonal Emails found:")
                    for email in personal_emails:
                        print(f"- {email}")
                else:
                    print("\nNo personal emails found")
                
                # Display phone numbers
                phones = profile.get('phone', [])
                if phones:
                    print("\nPhone numbers found:")
                    for phone in phones:
                        print(f"- {phone}")
                else:
                    print("\nNo phone numbers found")
                
                # Display GitHub profiles
                github_profiles = profile.get('github', [])
                if github_profiles:
                    print("\nGitHub profiles found:")
                    for github in github_profiles:
                        print(f"- {github}")
                else:
                    print("\nNo GitHub profiles found")
            else:
                print("\nNo profile data found in the response")
        else:
            print(f"\nError Response:")
            print(response.text)
            
            # Print response headers for debugging
            print("\nResponse Headers:")
            print(json.dumps(dict(response.headers), indent=2))
            
    except Exception as e:
        print(f"\nError occurred: {str(e)}")

if __name__ == "__main__":
    print("Starting ContactOut API test...")
    test_contactout_api() 