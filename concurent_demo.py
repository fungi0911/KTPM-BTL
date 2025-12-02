#!/usr/bin/env python3
"""Demo concurrent requests to test thread safety and circuit breaker behavior."""
import concurrent.futures
import requests
import time
from collections import Counter
import sys

BASE_URL = "http://127.0.0.1:5000"

def call_vendor_price(product_id: int, mode: str = "ok", request_id: int = 0):
    """Single request to vendor price endpoint."""
    url = f"{BASE_URL}/warehouse_items/vendor_price/{product_id}"
    params = {"mode": mode}
    
    try:
        start = time.time()
        resp = requests.get(url, params=params, timeout=10)
        duration = time.time() - start
        
        data = resp.json() if resp.ok else {}
        return {
            "request_id": request_id,
            "status": resp.status_code,
            "attempts": data.get("attempts", 1) if resp.ok else 0,
            "state": data.get("state", {}).get("state", "unknown") if resp.ok else "error",
            "duration": round(duration, 2),
            "success": resp.ok,
        }
    except Exception as e:
        return {
            "request_id": request_id,
            "status": 0,
            "error": str(e),
            "success": False,
        }


def print_header(title):
    """Print formatted header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def demo_normal_concurrent():
    """Demo: 20 concurrent requests with vendor OK."""
    print_header("DEMO 1: Concurrent Requests - Vendor Normal (OK mode)")
    
    num_requests = 20
    results = []
    
    print(f"\n→ Sending {num_requests} concurrent requests to vendor...")
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(call_vendor_price, product_id=i % 5 + 1, mode="ok", request_id=i)
            for i in range(num_requests)
        ]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    total_time = time.time() - start_time
    
    # Analyze results
    success_count = sum(1 for r in results if r.get("success"))
    states = Counter(r.get("state", "unknown") for r in results)
    avg_duration = sum(r.get("duration", 0) for r in results) / len(results)
    
    print(f"\n✓ Results:")
    print(f"  • Total requests: {num_requests}")
    print(f"  • Successful: {success_count} ({success_count/num_requests*100:.1f}%)")
    print(f"  • Failed: {num_requests - success_count}")
    print(f"  • Circuit states: {dict(states)}")
    print(f"  • Avg response time: {avg_duration:.3f}s")
    print(f"  • Total time: {total_time:.2f}s")
    print(f"  • Throughput: {num_requests/total_time:.2f} req/s")


def demo_concurrent_circuit_open():
    """Demo: Force circuit to open with concurrent failing requests."""
    print_header("DEMO 2: Circuit Breaker - Force Open with Failures")
    
    # Phase 1: Trigger circuit open
    print("\n→ Phase 1: Send 10 failing requests to open circuit...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(call_vendor_price, product_id=1, mode="down", request_id=i)
            for i in range(10)
        ]
        phase1_results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    phase1_status = Counter(r.get("status") for r in phase1_results)
    phase1_states = Counter(r.get("state", "unknown") for r in phase1_results)
    
    print(f"  • Status codes: {dict(phase1_status)}")
    print(f"  • Circuit states: {dict(phase1_states)}")
    
    # Check state
    time.sleep(0.5)
    state_resp = requests.get(f"{BASE_URL}/warehouse_items/vendor_state")
    state_data = state_resp.json()
    current_state = state_data.get("state", "unknown")
    fail_counter = state_data.get("fail_counter", 0)
    
    print(f"\n→ Circuit State After Failures:")
    print(f"  • State: {current_state.upper()}")
    print(f"  • Fail counter: {fail_counter}/5")
    
    # Phase 2: Try more requests while circuit is open
    print("\n→ Phase 2: Send 10 requests (circuit should be OPEN)...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(call_vendor_price, product_id=1, mode="ok", request_id=i+10)
            for i in range(10)
        ]
        phase2_results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    phase2_status = Counter(r.get("status") for r in phase2_results)
    circuit_open_count = sum(1 for r in phase2_results if r.get("status") == 503)
    
    print(f"  • Status codes: {dict(phase2_status)}")
    print(f"  • Circuit open rejections (503): {circuit_open_count}/10")
    print(f"\n✓ Expected: All requests should be rejected with 503 (circuit open)")


def demo_concurrent_flaky_vendor():
    """Demo: Concurrent requests with flaky vendor (retry behavior)."""
    print_header("DEMO 3: Retry Logic - Flaky Vendor (50% fail rate)")
    
    num_requests = 30
    
    print(f"\n→ Sending {num_requests} concurrent requests to flaky vendor...")
    start_time = time.time()
    
    # Use lambda to capture index
    def make_request(i):
        return call_vendor_price(
            product_id=i % 5 + 1, 
            mode="flaky", 
            request_id=i
        )
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(make_request, range(num_requests)))
    
    total_time = time.time() - start_time
    
    # Analyze retry behavior
    success_count = sum(1 for r in results if r.get("success"))
    attempts_dist = Counter(r.get("attempts", 0) for r in results if r.get("success"))
    status_codes = Counter(r.get("status") for r in results)
    
    print(f"\n✓ Results:")
    print(f"  • Total requests: {num_requests}")
    print(f"  • Successful: {success_count} ({success_count/num_requests*100:.1f}%)")
    print(f"  • Failed: {num_requests - success_count}")
    print(f"  • Status codes: {dict(status_codes)}")
    print(f"  • Retry attempts distribution:")
    for attempts, count in sorted(attempts_dist.items()):
        print(f"    - {attempts} attempt(s): {count} requests")
    print(f"  • Total time: {total_time:.2f}s")
    
    # Get final metrics
    state_resp = requests.get(f"{BASE_URL}/warehouse_items/vendor_state")
    metrics = state_resp.json().get("metrics", {})
    print(f"\n→ Final Metrics:")
    print(f"  • Total calls: {metrics.get('calls', 0)}")
    print(f"  • Successes: {metrics.get('successes', 0)}")
    print(f"  • Failures: {metrics.get('failures', 0)}")
    print(f"  • Total retry attempts: {metrics.get('retry_attempts_total', 0)}")


def demo_circuit_recovery():
    """Demo: Circuit breaker recovery (half-open -> closed)."""
    print_header("DEMO 4: Circuit Recovery - Half-Open to Closed")
    
    # First, open the circuit
    print("\n→ Step 1: Open circuit with 5 failures...")
    for i in range(5):
        resp = requests.get(f"{BASE_URL}/warehouse_items/vendor_price/1?mode=down")
        print(f"  • Request {i+1}: {resp.status_code}")
    
    state_resp = requests.get(f"{BASE_URL}/warehouse_items/vendor_state")
    state = state_resp.json().get("state", "unknown")
    print(f"\n→ Circuit state: {state.upper()}")
    
    # Wait for recovery timeout
    recovery_time = 15
    print(f"\n→ Step 2: Waiting {recovery_time}s for recovery timeout...")
    for i in range(recovery_time, 0, -1):
        sys.stdout.write(f"\r  • Time remaining: {i}s ")
        sys.stdout.flush()
        time.sleep(1)
    print("\n")
    
    # Send successful request to close circuit
    print("→ Step 3: Send successful request (half-open)...")
    resp = requests.get(f"{BASE_URL}/warehouse_items/vendor_price/1?mode=ok")
    data = resp.json()
    
    print(f"  • Status: {resp.status_code}")
    print(f"  • Circuit state: {data.get('state', {}).get('state', 'unknown').upper()}")
    
    # Verify circuit is closed
    state_resp = requests.get(f"{BASE_URL}/warehouse_items/vendor_state")
    final_state = state_resp.json().get("state", "unknown")
    state_changes = state_resp.json().get("metrics", {}).get("state_changes", 0)
    
    print(f"\n✓ Final State:")
    print(f"  • Circuit: {final_state.upper()}")
    print(f"  • State changes: {state_changes}")
    print(f"  • Expected: closed -> open -> half-open -> closed")


def demo_comparison_with_without_resilience():
    """Demo: Compare with and without resilience."""
    print_header("DEMO 5: Comparison - With vs Without Resilience")
    
    # Without resilience
    print("\n→ Test 1: WITHOUT resilience (raw mode) - Flaky vendor")
    failures_raw = 0
    for i in range(10):
        resp = requests.get(
            f"{BASE_URL}/warehouse_items/vendor_price/1",
            params={"mode": "flaky", "fail_rate": "0.7", "strategy": "raw"}
        )
        if not resp.ok:
            failures_raw += 1
    
    print(f"  • Failures: {failures_raw}/10 ({failures_raw*10}%)")
    
    # With resilience
    print("\n→ Test 2: WITH resilience (default mode) - Flaky vendor")
    failures_resilient = 0
    total_attempts = 0
    for i in range(10):
        resp = requests.get(
            f"{BASE_URL}/warehouse_items/vendor_price/1",
            params={"mode": "flaky", "fail_rate": "0.7"}
        )
        if resp.ok:
            total_attempts += resp.json().get("attempts", 1)
        else:
            failures_resilient += 1
    
    avg_attempts = total_attempts / (10 - failures_resilient) if failures_resilient < 10 else 0
    
    print(f"  • Failures: {failures_resilient}/10 ({failures_resilient*10}%)")
    print(f"  • Avg retry attempts: {avg_attempts:.1f}")
    
    print(f"\n✓ Comparison:")
    print(f"  • Without resilience: {failures_raw} failures")
    print(f"  • With resilience: {failures_resilient} failures")
    print(f"  • Improvement: {((failures_raw - failures_resilient) / failures_raw * 100):.1f}%" if failures_raw > 0 else "N/A")


def demo_load_test():
    """Demo: Heavy load test."""
    print_header("DEMO 6: Load Test - 100 Concurrent Requests")
    
    num_requests = 100
    
    def make_request(i):
        # Mix scenarios
        if i % 10 == 0:
            mode = "down"  # 10% down
        elif i % 3 == 0:
            mode = "flaky"  # 33% flaky
        else:
            mode = "ok"  # Rest OK
        
        return call_vendor_price(product_id=i % 10 + 1, mode=mode, request_id=i)
    
    print(f"\n→ Sending {num_requests} requests with mixed scenarios...")
    print(f"  • 10% down, 33% flaky, 57% ok")
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(make_request, range(num_requests)))
    
    total_duration = time.time() - start_time
    
    # Analyze
    success_count = sum(1 for r in results if r.get("success"))
    status_codes = Counter(r.get("status") for r in results)
    states = Counter(r.get("state", "unknown") for r in results)
    
    print(f"\n✓ Load Test Results:")
    print(f"  • Total requests: {num_requests}")
    print(f"  • Total duration: {total_duration:.2f}s")
    print(f"  • Throughput: {num_requests / total_duration:.2f} req/s")
    print(f"  • Successful: {success_count} ({success_count/num_requests*100:.1f}%)")
    print(f"  • Failed: {num_requests - success_count}")
    print(f"  • Status codes: {dict(status_codes)}")
    print(f"  • Circuit states distribution: {dict(states)}")
    
    # Final state
    state_resp = requests.get(f"{BASE_URL}/warehouse_items/vendor_state")
    data = state_resp.json()
    
    print(f"\n→ Final System State:")
    print(f"  • Circuit state: {data.get('state', 'unknown').upper()}")
    print(f"  • Metrics: {data.get('metrics', {})}")


def main():
    print("\n" + "="*70)
    print("     CIRCUIT BREAKER + RETRY - COMPREHENSIVE DEMO")
    print("="*70)
    print("\nThis demo will showcase:")
    print("  1. Normal concurrent operations")
    print("  2. Circuit breaker opening on failures")
    print("  3. Retry logic with flaky vendor")
    print("  4. Circuit recovery process")
    print("  5. Comparison with/without resilience")
    print("  6. Load testing")
    print("\nMake sure Flask server is running on http://127.0.0.1:5000")
    
    input("\nPress Enter to start demos...")
    
    try:
        demo_normal_concurrent()
        time.sleep(2)
        
        demo_concurrent_circuit_open()
        
        # Wait for circuit to close before next demo
        print("\n→ Waiting 20s for circuit to reset...")
        time.sleep(20)
        
        demo_concurrent_flaky_vendor()
        time.sleep(2)
        
        demo_circuit_recovery()
        time.sleep(2)
        
        demo_comparison_with_without_resilience()
        time.sleep(2)
        
        demo_load_test()
        
        print_header("ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("\n✓ Key Takeaways:")
        print("  • Circuit breaker protects system from cascading failures")
        print("  • Retry logic increases success rate with transient errors")
        print("  • Thread-safe implementation handles concurrent requests")
        print("  • Metrics provide visibility into system behavior")
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()