import requests
import sys
import json
from datetime import datetime
import time

class SerenityAPITester:
    def __init__(self, base_url="https://student-wellness-7.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.user_id = "student_123"
        self.session_id = f"test_session_{datetime.now().strftime('%H%M%S')}"

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}" if endpoint else self.base_url
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_base_endpoint(self):
        """Test base API endpoint"""
        return self.run_test("Base API Endpoint", "GET", "", 200)

    def test_create_journal_entry(self):
        """Test creating a journal entry with AI analysis"""
        journal_data = {
            "user_id": self.user_id,
            "content": "I'm feeling really stressed about my upcoming exams. There's so much to study and I don't know if I'll be ready in time. I keep procrastinating and then feeling guilty about it.",
            "tags": ["stress", "exams", "anxiety"],
            "privacy_level": "private"
        }
        
        success, response = self.run_test(
            "Create Journal Entry with AI Analysis",
            "POST",
            "journal",
            200,
            data=journal_data,
            timeout=45  # AI analysis takes time
        )
        
        if success and response:
            # Verify AI analysis fields are present
            required_fields = ['sentiment', 'mood_score', 'ai_insights']
            for field in required_fields:
                if field not in response:
                    print(f"⚠️  Warning: Missing AI analysis field '{field}'")
                else:
                    print(f"   AI {field}: {response[field]}")
            return response.get('id')
        return None

    def test_get_journal_entries(self):
        """Test retrieving journal entries"""
        return self.run_test(
            "Get Journal Entries",
            "GET",
            f"journal/{self.user_id}",
            200
        )

    def test_chat_with_companion(self):
        """Test chat functionality with AI companion"""
        chat_data = {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "message": "I'm feeling overwhelmed with my coursework. Can you help me with some coping strategies?"
        }
        
        success, response = self.run_test(
            "Chat with AI Companion",
            "POST",
            "chat",
            200,
            data=chat_data,
            timeout=45  # AI response takes time
        )
        
        if success and response:
            print(f"   AI Response: {response.get('response', 'No response')[:100]}...")
            print(f"   Message Sentiment: {response.get('sentiment', 'Unknown')}")
        
        return success

    def test_get_chat_history(self):
        """Test retrieving chat history"""
        return self.run_test(
            "Get Chat History",
            "GET",
            f"chat/{self.user_id}/{self.session_id}",
            200
        )

    def test_create_mood_checkin(self):
        """Test creating a mood check-in"""
        mood_data = {
            "user_id": self.user_id,
            "mood_level": 3,
            "stress_level": 4,
            "energy_level": 2,
            "notes": "Feeling tired and stressed about upcoming deadlines"
        }
        
        success, response = self.run_test(
            "Create Mood Check-in",
            "POST",
            "mood-checkin",
            200,
            data=mood_data
        )
        
        if success and response:
            print(f"   Mood: {response.get('mood_level')}/5")
            print(f"   Stress: {response.get('stress_level')}/5")
            print(f"   Energy: {response.get('energy_level')}/5")
        
        return success

    def test_get_mood_checkins(self):
        """Test retrieving mood check-ins"""
        return self.run_test(
            "Get Mood Check-ins",
            "GET",
            f"mood-checkin/{self.user_id}",
            200
        )

    def test_get_user_stats(self):
        """Test retrieving user statistics with AI recommendations"""
        success, response = self.run_test(
            "Get User Statistics",
            "GET",
            f"stats/{self.user_id}",
            200
        )
        
        if success and response:
            print(f"   Total Entries: {response.get('total_entries', 0)}")
            print(f"   Avg Mood: {response.get('avg_mood', 0)}")
            print(f"   Avg Stress: {response.get('avg_stress', 0)}")
            print(f"   Recommendations: {len(response.get('recommendations', []))}")
        
        return success

def main():
    print("🧘 Starting Serenity Student API Tests")
    print("=" * 50)
    
    tester = SerenityAPITester()
    
    # Test sequence
    print("\n📡 Testing Base Connectivity...")
    tester.test_base_endpoint()
    
    print("\n📝 Testing Journal Functionality...")
    journal_id = tester.test_create_journal_entry()
    time.sleep(2)  # Brief pause between tests
    tester.test_get_journal_entries()
    
    print("\n💬 Testing Chat Functionality...")
    tester.test_chat_with_companion()
    time.sleep(2)
    tester.test_get_chat_history()
    
    print("\n😊 Testing Mood Check-in Functionality...")
    tester.test_create_mood_checkin()
    time.sleep(1)
    tester.test_get_mood_checkins()
    
    print("\n📊 Testing Analytics...")
    tester.test_get_user_stats()
    
    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed! Backend is working correctly.")
        return 0
    else:
        failed_tests = tester.tests_run - tester.tests_passed
        print(f"⚠️  {failed_tests} test(s) failed. Check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())