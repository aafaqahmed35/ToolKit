# Linux Chunk 3 of 6 — Networking & Connectivity Debugging

Phase I · Developer Foundations  
Backend Engineering Handbook

Source file: `content/linux/03-networking-connectivity-debugging.md`

Your Spring Boot API is running. The database is running. Yet the application cannot connect to PostgreSQL, your API returns a timeout, or a domain name refuses to resolve.

How do you find the actual failure instead of randomly restarting services?

This chunk gives you a systematic, command-line approach to diagnosing network connectivity on Linux, with examples that apply directly to backend engineering.

---

## The Three Learning Layers

| Layer | Focus & Objective |
| :--- | :--- |
| **Layer 1 — Fundamentals & Mental Models** | DNS, IP addresses, ports, sockets, TCP, routing and connection failures |
| **Layer 2 — Practical Engineering & Workflows** | `curl`, `dig`, `ss`, `ip`, `nc`, `ping`, `traceroute` and systematic troubleshooting |
| **Layer 3 — Production Engineering & Interview Mastery** | Debug DNS failures, refused connections, timeouts, container networking and intermittent backend outages |

---

# LAYER 1 — FUNDAMENTALS & MENTAL MODELS

## 1.1 The journey of a backend request

Imagine a client sending a request to your Spring Boot service:

```
Client
  |
  v
DNS resolution
  |
  v
Destination IP address
  |
  v
Routing and network path
  |
  v
TCP connection to destination port
  |
  v
TLS handshake, if HTTPS
  |
  v
HTTP request
  |
  v
Application response
```

Each stage can fail independently:

- **DNS fails**: the client cannot resolve the hostname.
- **Routing fails**: packets cannot reach the destination.
- **TCP fails**: the destination port is unreachable, closed, or filtered.
- **TLS fails**: the network connection exists, but cryptographic negotiation fails.
- **HTTP fails**: the server responds with an HTTP error (`4xx`/`5xx`).
- **Application logic fails**: the request reaches your backend, but the backend cannot fulfill it (e.g. database timeout).

These failures can look similar to an end user, but their root causes and operational fixes differ completely.

---

## 1.2 IP addresses and ports

An IP address identifies a network interface or endpoint address. A port identifies a transport-layer endpoint associated with an application process.

Common backend ports:

| Port | Typical use |
| :---: | :--- |
| `22` | SSH |
| `53` | DNS |
| `80` | HTTP |
| `443` | HTTPS |
| `5432` | PostgreSQL |
| `6379` | Redis |
| `8080` | Common application HTTP port (e.g. Spring Boot) |
| `9090` | Common Prometheus server port |

These are conventional defaults, not guarantees. Applications can use different ports, and a port being open does not prove the application is healthy.

Consider:

```text
127.0.0.1:8080
```

- `127.0.0.1` is the IPv4 loopback address.
- `8080` is the destination port.
- The address refers to the current network namespace's loopback interface.

**Critical container insight:** `localhost` inside a container refers to that container's own network namespace, not automatically to your host machine or another container.

---

## 1.3 DNS: translating names into addresses

DNS translates human-readable domain names such as `api.example.com` into IP records that clients use to locate services.

Common record types:

- **`A`** — IPv4 address record.
- **`AAAA`** — IPv6 address record.
- **`CNAME`** — Canonical name (alias to another DNS name).
- **`MX`** — Mail exchange server record.
- **`TXT`** — Arbitrary text data, often used for domain verification and SPF/DKIM security policies.

When your application connects to a hostname, it resolves that hostname before initiating a TCP connection. Caching, resolver configuration, search domains, and multiple address records can affect the result.

Inspect DNS records with:

```bash
dig api.example.com
dig A api.example.com
dig AAAA api.example.com
```

If `dig` is unavailable, some environments provide `nslookup` or `getent`:

```bash
getent hosts api.example.com
```

`getent` is particularly useful because it follows the system's configured name-resolution mechanisms (`/etc/nsswitch.conf`, `/etc/hosts`, and DNS) rather than querying DNS in isolation.

**Important distinction:** DNS resolution success proves that a name-resolution path returned an address. It does not prove that the destination is reachable or accepting connections.

---

## 1.4 TCP: establishing a connection

TCP provides a reliable, ordered byte stream between network endpoints.

A simplified TCP connection establishment is the three-way handshake:

```
Client                             Server
  |                                  |
  | -------- SYN (seq=x) ----------> |  1. Client requests connection
  |                                  |
  | <--- SYN-ACK (seq=y, ack=x+1) -- |  2. Server acknowledges and responds
  |                                  |
  | -------- ACK (ack=y+1) --------> |  3. Client confirms; connection established
  |                                  |
```

A TCP connection is identified by the 4-tuple:
`{Source IP, Source Port, Destination IP, Destination Port}` + Protocol (TCP).

Useful concepts:

- **Listening socket**: a server endpoint bound to an address and port waiting for incoming connections.
- **Ephemeral port**: a temporary, dynamic source port allocated by the OS kernel for the client side of the connection.
- **Connection refused (`RST`)**: the connection attempt was actively rejected, commonly because nothing is listening on that address/port or a firewall sent a TCP Reset.
- **Connection timeout**: the operation did not complete within the timeout deadline; packets may be silently dropped by a firewall, the routing path may be broken, or the remote server may be completely unresponsive.
- **Connection reset (`ECONNRESET`)**: an established connection was forcibly aborted by the remote peer or an intermediate proxy/NAT box.

These are diagnostic clues, not absolute proof of a single cause.

---

## 1.5 Listening ports and sockets

Your backend may be running, but it might be listening on the wrong address.

Compare:

```text
127.0.0.1:8080
```

with:

```text
0.0.0.0:8080
```

- `127.0.0.1:8080` binds strictly to the IPv4 loopback interface. It accepts traffic only from processes running inside the same machine/container.
- `0.0.0.0:8080` binds to all local IPv4 network interfaces. It accepts traffic arriving from external network interfaces, container bridges, and loopback.

An application listening only on loopback may be reachable locally but completely unavailable to external callers or ingress proxies.

For IPv6, `::` is commonly used as a wildcard address, though its exact interaction with IPv4 depends on socket configuration (`IPV6_V6ONLY`).

Inspect listening sockets with:

```bash
ss -lntp
```

Flags:
- `-l` — show only listening sockets.
- `-n` — show numeric IP addresses and port numbers (avoids slow DNS reverse lookups).
- `-t` — display TCP sockets.
- `-p` — display the process name and PID owning the socket (requires `sudo` for full visibility).

Add `-u` to inspect UDP sockets as well (`ss -lntup`).

---

## 1.6 Routing: how packets find their destination

Routing determines which network interface or next-hop gateway the kernel uses for an IP destination.

Inspect interfaces and IP addresses:

```bash
ip addr
```

Inspect the routing table:

```bash
ip route
```

Inspect the route the kernel selects toward a specific destination:

```bash
ip route get 93.184.216.34
```

A correct local route does not guarantee end-to-end reachability. Security groups, local firewalls (`iptables`/`nftables`), upstream routing, and intermediate NAT gateways may still block traffic.

---

## 1.7 ICMP and the limits of ping

`ping` sends ICMP Echo Requests and waits for ICMP Echo Replies.

```bash
ping -c 4 example.com
```

It can help investigate basic network reachability and packet round-trip time (RTT), but:

- Many production servers, cloud VPCs, and load balancers deliberately block ICMP.
- Firewalls commonly drop ICMP while allowing application TCP traffic (ports 80, 443).
- A successful ping does not prove that port `443` or `5432` is open and healthy.
- DNS resolution performed by `ping` can introduce an additional variable.

**Therefore, ping failure does not necessarily mean the service is down.**

---

## 1.8 HTTP, HTTPS and TLS

Once a TCP connection is established, HTTP traffic can be exchanged. HTTPS adds a TLS handshake over the TCP connection to protect communication and authenticate the server via certificate validation.

A useful test:

```bash
curl -v --connect-timeout 5 https://example.com/
```

The verbose output helps you observe:
1. DNS resolution IP.
2. TCP connection handshake (`Connected to... port 443`).
3. TLS cryptographic negotiation (cipher suite, server certificate chain).
4. HTTP request headers sent (`> GET / HTTP/1.1`).
5. HTTP response headers received (`< HTTP/1.1 200 OK`).

An HTTP `401`, `403`, `500`, or `502` means the network connection succeeded and the client received an HTTP response from an upstream server. It is fundamentally different from a failure to establish the network connection in the first place.

---

# LAYER 2 — PRACTICAL ENGINEERING & WORKFLOWS

## 2.1 Your network-debugging command kit

| Tool | Primary Purpose & Typical Command |
| :--- | :--- |
| **`dig`** | Query DNS records and inspect name resolution (`dig api.example.com`) |
| **`getent hosts`** | Check hostname resolution through OS resolver (`getent hosts api.example.com`) |
| **`ss -lntp`** | Find TCP listening sockets and associated process PIDs |
| **`ip addr`** | Inspect network interfaces, MAC addresses, and assigned IPs |
| **`ip route`** | Inspect routing-table entries and default gateways |
| **`nc -zv`** | Test whether a TCP port is open and accepting handshakes (`nc -zv host 5432`) |
| **`curl -v`** | Inspect HTTP behavior, connection establishment, TLS certificates, and latency |
| **`ping`** | Test ICMP round-trip latency and packet loss where allowed |
| **`traceroute`** | Trace the intermediate routing hops to an IP target |
| **`lsof -i`** | Inspect processes and open network sockets (`lsof -i :8080`) |

Some utilities may not be installed by default in minimal container images. Know which alternatives exist (e.g. `getent` vs. `dig`, `curl` vs. `nc`).

---

## 2.2 Find out whether your backend is listening

Suppose your Spring Boot service should accept requests on port `8080`:

```bash
sudo ss -lntp
```

To filter for port `8080`:

```bash
sudo ss -lntp | grep ':8080'
```

If nothing appears, possibilities include:

- The application crashed during startup.
- It is listening on a different port (e.g. `8081`).
- It is bound to a different network namespace or loopback only.
- You lack permission to see process details (`sudo` displays the owning PID).

Inspect the process separately:

```bash
pgrep -af java
```

Then check the application logs for binding errors (such as `Port already in use`).

---

## 2.3 Test connectivity to a destination port

For a PostgreSQL service:

```bash
nc -zv db.example.internal 5432
```

For an HTTPS endpoint:

```bash
nc -zv api.example.com 443
```

A successful TCP connection test (`Connection to db.example.internal 5432 port [tcp/*] succeeded!`) confirms that the TCP 3-way handshake succeeded. It does not validate database credentials, application protocols, or pool health.

If `nc` is unavailable, `curl` or a lightweight bash socket test can be used:

```bash
(echo > /dev/tcp/db.example.internal/5432) >/dev/null 2>&1 && echo "Open" || echo "Closed"
```

---

## 2.4 Use curl to separate connection failures from HTTP failures

Start with a targeted probe:

```bash
curl -v --connect-timeout 5 --max-time 15 https://api.example.com/health
```

Flags:
- `--connect-timeout 5`: bounds the time allowed to establish the TCP connection.
- `--max-time 15`: bounds the total round-trip request/response duration.
- `-v`: prints detailed connection, TLS, and header diagnostics.

Inspect the result:

| Observation | What it suggests | Actionable Next Step |
| :--- | :--- | :--- |
| `Could not resolve host` | Name resolution failed | Check DNS, `/etc/resolv.conf`, search domains |
| `Connection refused` | TCP connection actively rejected | Check listener on destination IP:port, firewalls |
| Connection timeout | Packets dropped or route blackholed | Check security groups, cloud VPC routing, server health |
| TLS certificate error | Certificate expired, untrusted, or name mismatch | Inspect certificate validity (`openssl s_client`) |
| HTTP `401` or `403` | Authentication or authorization rejected | Verify API keys, JWT tokens, header permissions |
| HTTP `500` | Application threw an unhandled exception | Inspect backend server logs |
| HTTP `502` / `504` | Upstream gateway or reverse proxy error/timeout | Check upstream service process and proxy timeouts |
| HTTP `200` | Successful HTTP response | Protocol healthy; verify payload correctness |

---

## 2.5 Diagnose DNS properly

Try:

```bash
dig api.example.com
getent hosts api.example.com
```

Compare the results:
- **Both fail**: Investigate hostname spelling, `/etc/resolv.conf` nameservers, and whether the record exists in DNS.
- **`dig` succeeds but `getent` fails**: Inspect the system's resolver configuration in `/etc/nsswitch.conf` (e.g. bad `hosts:` entry order or broken local caching daemon).
- **Resolves to unexpected address**: Check split-horizon DNS, internal private DNS zones vs. public zones, and local `/etc/hosts` overrides.
- **Resolves correctly but connection fails**: Name resolution is working; immediately move down the stack to routing and TCP port reachability.

Do not touch DNS records when a connection times out if DNS resolves instantly!

---

## 2.6 Inspect local network configuration

```bash
ip addr
ip route
```

These commands answer different questions:
- `ip addr`: Which network interfaces exist, are they `UP`, and which IPs are assigned?
- `ip route`: What is the default gateway (`default via ...`), and are specific subnets routed through dedicated interfaces?
- `ip route get DESTINATION_IP`: Which exact interface and source IP will the kernel select to reach that destination?

On macOS, equivalent tools include:
```bash
ifconfig
netstat -rn
```

---

## 2.7 Investigate a port conflict

Suppose Spring Boot fails to start with:
`Web server failed to start. Port 8080 was already in use.`

Inspect the port:

```bash
sudo ss -lntp | grep ':8080'
```

Or, if available:

```bash
sudo lsof -iTCP:8080 -sTCP:LISTEN
```

Resolution workflow:
1. Identify the owning PID and process name from the output.
2. Determine whether it is an old zombie instance of your app or a legitimate background service.
3. Check whether your application should be reconfigured to a different port (`server.port=8081`).
4. Gracefully terminate the old process if appropriate (`kill -TERM PID`).
5. Restart your application and verify the new listener.

**Never kill an unfamiliar process without verifying its identity and purpose.**

---

## 2.8 Understand connection states

Inspect TCP socket states:

```bash
ss -ant
```

Useful states:

| State | Meaning | Practical Significance |
| :--- | :--- | :--- |
| `LISTEN` | Server socket waiting for connections | Application ready to accept traffic |
| `ESTAB` | Fully established connection | Active data exchange occurring |
| `SYN-SENT` | Client sent SYN; awaiting SYN-ACK | Network path issue, packet loss, or firewall drop |
| `TIME-WAIT` | Local endpoint closed connection; waiting 2*MSL | Normal TCP cleanup; high volume can exhaust ephemeral ports |
| `CLOSE-WAIT` | Remote closed connection; local app hasn't closed | Potential connection leak in application code |

Many connections in `TIME-WAIT` are a normal consequence of short-lived HTTP connections. A persistent accumulation of `CLOSE-WAIT` connections indicates an application bug where sockets are abandoned without being closed.

---

## 2.9 Test the network path

Trace routing hops toward a target:

```bash
traceroute example.com
```

*(On minimal Linux distros, `tracepath` is often pre-installed).*

A traceroute may reveal where packets stop responding, but remember that intermediate core routers often deprioritize or filter ICMP/UDP probes while forwarding TCP traffic at line speed.

For web services, combine with:

```bash
curl -v --connect-timeout 5 https://example.com/
```

Combine evidence from multiple layers rather than relying on a single diagnostic tool.

---

# LAYER 3 — PRODUCTION ENGINEERING & INTERVIEW MASTERY

## 3.1 The connectivity troubleshooting decision tree

Use this systematic framework when an application cannot reach an upstream dependency:

```
Client Cannot Reach Backend
       |
       +---> 1. Can the hostname resolve?
       |     `dig HOST` or `getent hosts HOST`
       |     [NO] -> Check DNS, /etc/resolv.conf, split-horizon, /etc/hosts
       |     [YES] -> Proceed to Step 2
       |
       +---> 2. Is destination reachable on TCP port?
       |     `nc -zv HOST PORT`
       |     [REFUSED] -> Target not listening on IP:port, or crash. Check service.
       |     [TIMEOUT] -> Packets dropped by firewall, security group, or routing.
       |     [SUCCESS] -> Proceed to Step 3
       |
       +---> 3. Does application protocol negotiate?
       |     `curl -v URL`
       |     [TLS ERROR] -> Expired/mismatched cert, truststore missing CA.
       |     [HTTP 4xx]  -> Auth, permission, or routing path error.
       |     [HTTP 5xx]  -> Application error or proxy upstream failure.
       |     [HTTP 200]  -> Protocol healthy.
       |
       +---> 4. Verify Root Cause & Document Fix
```

---

## 3.2 Incident A — Connection refused

**Scenario:** A backend service attempts to connect to PostgreSQL at `127.0.0.1:5432` and fails with `Connection refused`.

### Potential root causes:
1. PostgreSQL service is stopped or crashed.
2. PostgreSQL is listening on a different port.
3. PostgreSQL is bound to an internal Docker bridge or physical interface, but not `127.0.0.1` (`listen_addresses` in `postgresql.conf`).
4. The client is inside a container, where `127.0.0.1` resolves to the container itself rather than the database host.
5. A host firewall actively rejects the port.

### Investigation commands:
```bash
sudo ss -lntp | grep ':5432'
pgrep -af postgres
```

**Production lesson:** `Connection refused` indicates an active rejection (TCP `RST`), proving the network path exists but no listening socket accepted the handshake on that IP and port.

---

## 3.3 Incident B — Connection timeout

**Scenario:** A backend connects to a remote Redis cache at `redis.prod.internal:6379` and times out after 10 seconds.

### Investigation workflow:
1. **Confirm exact endpoint**: Verify hostname and port from application configuration.
2. **DNS verification**: Run `getent hosts redis.prod.internal` from inside the application container/host.
3. **TCP probe**: Run `nc -zv redis.prod.internal 6379`.
4. **Security group / Network policy check**: Verify that egress rules on the client and ingress rules on Redis permit traffic on port 6379.
5. **Inspect destination**: Log into the Redis host and run `ss -lntp | grep ':6379'` to verify it is bound to `0.0.0.0` or its VPC IP.

**Production lesson:** Always execute network diagnostics from the exact network namespace of the failing client. A test from your laptop does not prove a Kubernetes pod or cloud VM can connect.

---

## 3.4 Incident C — Docker networking mistake

**Scenario:** A Spring Boot container and a PostgreSQL container are deployed locally. Spring Boot uses:
```properties
spring.datasource.url=jdbc:postgresql://localhost:5432/mydb
```
The application fails with `Connection refused`.

### The root cause:
Inside a Docker container, `localhost` (`127.0.0.1`) refers strictly to the container's own isolated network namespace. It does **not** refer to the host machine or another container.

### The correction:
In Docker Compose, containers communicate across a user-defined bridge network using service names as DNS hostnames:
```properties
spring.datasource.url=jdbc:postgresql://postgres:5432/mydb
```
*(Assuming the PostgreSQL service is named `postgres` in `docker-compose.yml`).*

---

## 3.5 Incident D — Intermittent connection failures

**Scenario:** 1 in every 50 API requests to an external service fails with a connection error.

### Systematic investigation checklist:
1. **DNS round-robin**: Does `dig` return multiple IP addresses for the hostname, where one IP points to an unhealthy server?
2. **Connection pool exhaustion**: Is the application connection pool saturated, causing local threads to time out waiting for an idle socket?
3. **Ephemeral port exhaustion**: Are high connection volumes leaving thousands of sockets in `TIME-WAIT`, starving the kernel of source ports?
4. **Load balancer health checks**: Is an upstream load balancer periodically routing requests to a failing node?
5. **Transient packet loss / MTU issues**: Are packets dropping under peak network load?
6. **Retry storms**: Are client retries unthrottled, turning minor latency spikes into cascading outages?

**Production takeaway:** Collect exact timestamps. Correlate client error spikes with server socket counts (`ss -s`), pool metrics, and load balancer access logs.

---

## 3.6 Production debugging checklist

- [ ] Confirm exact hostname, port, and transport protocol.
- [ ] Test DNS resolution directly from the affected container or server.
- [ ] Inspect the destination host's listening socket (`ss -lntp`).
- [ ] Test TCP port connectivity using `nc -zv` or `curl -v`.
- [ ] Verify local interfaces (`ip addr`) and routing tables (`ip route`).
- [ ] Differentiate connection-layer failures from HTTP status codes (`4xx`/`5xx`).
- [ ] Inspect application and kernel logs around the failure timestamp.
- [ ] Confirm whether proxies, API gateways, or container NAT change the traffic path.
- [ ] Isolate the failing layer before modifying firewall or DNS configurations.
- [ ] Verify recovery with end-to-end synthetic requests and latency metrics.

---

# 4. Interview Mastery — 15 Core Questions & Answers

### Q1. What happens when you enter a URL in a browser or client?
**Answer**: 
1. **DNS Resolution**: The client resolves the hostname to an IP address (checking browser cache, OS cache, `/etc/hosts`, and recursive DNS resolvers).
2. **Routing & TCP Handshake**: The OS kernel initiates a 3-way TCP handshake (`SYN` → `SYN-ACK` → `ACK`) to the destination IP on port 80/443.
3. **TLS Handshake** (if HTTPS): Client and server negotiate cipher suites, authenticate server certificates, and derive symmetric encryption keys.
4. **HTTP Request & Response**: The client sends the HTTP request; the server processes it and returns an HTTP response code and payload.

### Q2. What is the difference between an IP address and a port?
**Answer**: An IP address operates at the Network layer (OSI Layer 3) to uniquely identify a host interface on a network. A port operates at the Transport layer (OSI Layer 4) to direct traffic to a specific application or process socket on that host.

### Q3. What does DNS do?
**Answer**: DNS (Domain Name System) translates human-readable domain names (e.g. `api.example.com`) into computer-routable IP addresses (e.g. `93.184.216.34`), eliminating the need for clients to hardcode IP addresses.

### Q4. What is the difference between `A` and `AAAA` records?
**Answer**: An `A` record maps a domain name to a 32-bit IPv4 address (e.g. `192.0.2.1`). An `AAAA` (quad-A) record maps a domain name to a 128-bit IPv6 address (e.g. `2001:db8::1`).

### Q5. What does `Connection refused` usually indicate?
**Answer**: It indicates an active rejection where the destination host sent back a TCP `RST` (Reset) packet. This typically occurs because no application is listening on that target IP and port, or a local firewall is configured to reject (rather than silently drop) connections.

### Q6. What does a `Connection timeout` indicate?
**Answer**: It indicates that the client sent a TCP `SYN` packet but received no response before its deadline expired. This is commonly caused by an intermediate firewall silently dropping packets, an incorrect routing table / blackhole, or an unresponsive server.

### Q7. What is a listening socket?
**Answer**: A listening socket is a network socket created by a server process, bound to an IP address and port, and placed into the `LISTEN` state to wait for and accept incoming client connection requests.

### Q8. What does `ss -lntp` show?
**Answer**: It displays all listening sockets (`-l`), with numeric IP addresses and ports (`-n`), for TCP sockets (`-t`), including the process name and PID owning each socket (`-p`).

### Q9. What is the TCP three-way handshake?
**Answer**: The protocol used to establish a reliable TCP connection:
1. **SYN**: Client sends a synchronize sequence number to the server.
2. **SYN-ACK**: Server acknowledges the client's sequence and sends its own synchronize sequence number.
3. **ACK**: Client acknowledges the server's sequence number; the socket transitions to `ESTABLISHED`.

### Q10. Why can `ping` fail while HTTPS works?
**Answer**: `ping` uses the ICMP protocol, whereas HTTPS uses TCP on port 443. Many corporate networks, cloud firewalls, and load balancers deliberately block ICMP for security while explicitly permitting TCP traffic on port 443.

### Q11. What is the difference between HTTP 500 and `Connection refused`?
**Answer**: `Connection refused` is a Transport-layer (Layer 4) failure where no TCP connection could be established. An HTTP 500 is an Application-layer (Layer 7) response, proving that DNS, routing, TCP, and TLS all succeeded, but the upstream application threw an unhandled server error.

### Q12. Why can `localhost` fail in Docker?
**Answer**: Each Docker container has its own isolated network namespace. `localhost` inside a container resolves to that specific container, not the host machine or peer containers. Peer containers on a bridge network must be addressed by their container or service name.

### Q13. What is the difference between TCP and UDP?
**Answer**: TCP is a connection-oriented, reliable protocol providing ordered byte delivery, flow control, and error recovery via retransmissions. UDP is a connectionless, unreliable protocol that transmits datagrams with minimal overhead and no delivery guarantees, used for DNS queries, video streaming, and metrics (StatsD).

### Q14. How would you debug a DNS issue?
**Answer**: 
1. Use `dig domain.com` to query the DNS server directly and check the `ANSWER SECTION` and response code (`NXDOMAIN`, `SERVFAIL`, `NOERROR`).
2. Use `getent hosts domain.com` to test system resolver resolution (including `/etc/hosts` and `/etc/nsswitch.conf`).
3. Check `/etc/resolv.conf` to verify configured nameservers and search domains.

### Q15. How would you debug a backend connectivity failure?
**Answer**: Follow the 4-layer diagnostic ladder:
1. **DNS**: Does `dig`/`getent` resolve the target IP?
2. **Port/TCP**: Does `nc -zv host port` establish a TCP connection?
3. **Routing/Firewall**: Check `ip route get IP` and security group / firewall rules if timing out.
4. **Application/TLS**: Use `curl -v URL` to inspect TLS certificates, headers, and HTTP status codes.

---

# 5. Hands-On Lab — Diagnose a Backend Connection

Complete this lab in your local development environment.

### Lab A — Check DNS and HTTP
Execute:
```bash
getent hosts example.com
dig example.com
curl -v --connect-timeout 5 --max-time 15 https://example.com/
```

Record:
- Did name resolution succeed?
- Which IP address was returned?
- Did TCP and TLS negotiation succeed?
- What HTTP status code was returned?

### Lab B — Inspect a local listener
If you have a local application or service running on port `8080` (or another test port):
```bash
ss -lntp | grep ':8080'
curl -v --connect-timeout 3 http://127.0.0.1:8080/
```
Verify whether the socket is bound to `127.0.0.1` or `0.0.0.0`, and inspect the server's response headers.

### Lab C — Write an incident diagnosis
Choose one of these failure symptoms:
- DNS lookup fails (`Could not resolve host`).
- TCP connection is refused (`Connection refused`).
- TCP connection times out (`Connection timed out`).
- TLS validation fails (`SSL certificate problem`).
- TCP succeeds but returns HTTP `502 Bad Gateway`.

For your chosen symptom, write down:
1. The failing network layer (Layer 3, 4, or 7).
2. Three specific commands you would run to isolate the cause.
3. Two plausible root causes.
4. The exact evidence that distinguishes those causes.
5. A safe remediation and recovery verification test.

---

# 6. Chunk 3 Mastery Checklist

### Layer 1 — Fundamentals & Mental Models
- [ ] Explain the complete path of a request (DNS → IP → Route → TCP → TLS → HTTP).
- [ ] Distinguish IP addresses (Layer 3) from port numbers (Layer 4).
- [ ] Explain DNS record types (`A`, `AAAA`, `CNAME`, `MX`, `TXT`).
- [ ] Describe the TCP 3-way handshake (`SYN`, `SYN-ACK`, `ACK`).
- [ ] Differentiate connection refusal (`RST`) from connection timeouts.
- [ ] Explain loopback binding (`127.0.0.1`) versus wildcard binding (`0.0.0.0`).
- [ ] Explain why `ping` (ICMP) is not a definitive test for web application health.

### Layer 2 — Practical Engineering & Workflows
- [ ] Inspect DNS resolution using `dig` and `getent hosts`.
- [ ] Inspect listening sockets and owning PIDs using `ss -lntp`.
- [ ] Probe TCP port connectivity using `nc -zv`.
- [ ] Differentiate network connection failures from HTTP status codes using `curl -v`.
- [ ] Inspect local network interfaces (`ip addr`) and routing tables (`ip route`).
- [ ] Resolve port conflicts methodically without blindly terminating unknown processes.
- [ ] Interpret TCP socket states (`LISTEN`, `ESTAB`, `TIME-WAIT`, `CLOSE-WAIT`).

### Layer 3 — Production Engineering & Interview Mastery
- [ ] Execute the systematic 4-step connectivity troubleshooting decision tree.
- [ ] Diagnose and resolve `Connection refused` in local and containerized services.
- [ ] Diagnose and isolate `Connection timeout` across firewalls and cloud VPCs.
- [ ] Explain and prevent the `localhost` network namespace trap in Docker.
- [ ] Investigate intermittent connection failures and connection pool leaks.
- [ ] Answer all 15 interview questions with technically sound engineering rationales.
- [ ] Complete the hands-on backend diagnostic lab.

---

## Chunk Completion Protocol
- Authoritative source file: `content/linux/03-networking-connectivity-debugging.md`.
- No chunk-level PDF generated.
- Complete Linux handbook PDF (`BEH_LINUX_COMPLETE_HANDBOOK.pdf`) is compiled only after all six Linux chunks are complete and verified.

---

## What Comes Next?

**Linux Chunk 4 of 6 — Logs, Permissions & System Troubleshooting**

We will cover:
- File permissions (read, write, execute), octal modes (`chmod 755`, `chmod 644`), ownership (`chown`), and `umask`.
- Special permissions (`SUID`, `SGID`, Sticky bit) and least-privilege principles.
- System and application logs: `/var/log/`, `syslog`, `auth.log`, and `journalctl` mastery.
- Log slicing and extraction with `grep`, `awk`, `cut`, `sed`, and `sort | uniq -c`.
- Disk space troubleshooting: `df -h`, `du -sh`, and unlinked open file descriptors.
- Incident simulations: permission denied on deploy, disk space exhausted, and log forensics.
- Practical lab and interview questions.
