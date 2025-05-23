"""Test script to verify the Prometheus metrics endpoint."""

import requests
import sys

def test_prometheus_endpoint(port=8080):
    """
    Test the Prometheus metrics endpoint.
    
    Args:
        port: Port the Prometheus server is running on
    """
    url = f"http://localhost:{port}/metrics"
    
    try:
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            print(f"✅ Successfully connected to Prometheus metrics endpoint")
            print("\nMetrics sample:")
            print("=" * 50)
            
            # Print a sample of the metrics (first 10 lines)
            lines = response.text.split("\n")
            for line in lines[:10]:
                print(line)
                
            if len(lines) > 10:
                print(f"... and {len(lines) - 10} more lines")
                
            print("=" * 50)
            return True
        else:
            print(f"❌ Failed to connect to Prometheus metrics endpoint: Status code {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Failed to connect to Prometheus metrics endpoint: Connection refused")
        return False
    except Exception as e:
        print(f"❌ Error testing Prometheus metrics endpoint: {str(e)}")
        return False

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    success = test_prometheus_endpoint(port)
    if not success:
        sys.exit(1)
