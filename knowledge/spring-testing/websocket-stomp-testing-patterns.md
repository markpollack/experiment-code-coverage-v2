---
source_project: n/a
derived_from:
  - plans/inbox/testing-deep-research-results/claude/websocket-stomp-testing.md
  - plans/inbox/testing-deep-research-results/chatgpt/patterns.md
  - plans/inbox/testing-deep-research-results/Google-Spring Testing Research Gaps.md
author: claude-code
created: 2026-03-02
last_verified: 2026-03-02
curation_status: verified
confidence: medium
task_types: [review, reference]
artifact_type: cheatsheet
subjects: [spring-testing, spring-websocket]
related:
  see_also:
    - spring/testing/webflux-testing-patterns.md
    - spring/testing/assertj-mockito-idioms.md
  broader: [spring/testing/index.md]
---

# WebSocket / STOMP Testing Patterns

Quick-reference for testing Spring WebSocket + STOMP endpoints. WebSocket tests require a **real server** — MockMvc and WebTestClient cannot complete a WebSocket handshake.

---

## Why RANDOM_PORT is Required

```java
// MockMvc operates on a mock DispatcherServlet — no real TCP socket.
// WebSocket upgrade requires a real HTTP connection.

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class OrderWebSocketTest {
    @LocalServerPort int port;
}
```

---

## StompClient Setup

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ChatWebSocketTest {

    @LocalServerPort int port;
    WebSocketStompClient stompClient;

    @BeforeEach
    void setUp() {
        stompClient = new WebSocketStompClient(new StandardWebSocketClient());
        stompClient.setMessageConverter(new MappingJackson2MessageConverter());
        stompClient.setDefaultHeartbeat(new long[]{0, 0});  // disable in tests
    }

    @AfterEach
    void tearDown() {
        stompClient.stop();  // prevent executor thread leaks
    }
}
```

---

## BlockingQueue Pattern — Send + Receive

```java
@Test
void sendMessage_broadcastsToSubscribers() throws Exception {
    BlockingQueue<ChatMessage> received = new LinkedBlockingQueue<>();

    String url = "ws://localhost:" + port + "/ws";
    StompSession session = stompClient
        .connectAsync(url, new StompSessionHandlerAdapter() {})
        .get(5, TimeUnit.SECONDS);

    session.subscribe("/topic/chat", new StompFrameHandler() {
        @Override
        public Type getPayloadType(StompHeaders headers) {
            return ChatMessage.class;
        }
        @Override
        public void handleFrame(StompHeaders headers, Object payload) {
            received.offer((ChatMessage) payload);
        }
    });

    session.send("/app/chat", new SendMessageRequest("alice", "Hello!"));

    ChatMessage msg = received.poll(5, TimeUnit.SECONDS);
    assertThat(msg).isNotNull();
    assertThat(msg.getSender()).isEqualTo("alice");
    assertThat(msg.getContent()).isEqualTo("Hello!");

    session.disconnect();
}
```

---

## Unit Test @MessageMapping Handlers Directly

```java
// Prefer this for handler logic — fast, no infrastructure needed
class ChatControllerUnitTest {

    ChatController controller = new ChatController();

    @Test
    void handleChat_returnsChatMessage() {
        SendMessageRequest req = new SendMessageRequest("alice", "Hello!");
        ChatMessage result = controller.handleChat(req);

        assertThat(result.getSender()).isEqualTo("alice");
        assertThat(result.getContent()).isEqualTo("Hello!");
        assertThat(result.getTimestamp()).isNotNull();
    }
}
```

---

## Testing @SendToUser (User-Targeted Messages)

```java
@Test
void sendPrivateMessage_deliveredToTargetUser() throws Exception {
    BlockingQueue<PrivateMessage> aliceReceived = new LinkedBlockingQueue<>();

    StompHeaders connectHeaders = new StompHeaders();
    connectHeaders.add("login", "alice");
    connectHeaders.add("passcode", "password");

    StompSession aliceSession = stompClient
        .connectAsync("ws://localhost:" + port + "/ws",
                       new WebSocketHttpHeaders(), connectHeaders,
                       new StompSessionHandlerAdapter() {})
        .get(5, TimeUnit.SECONDS);

    aliceSession.subscribe("/user/queue/messages", new StompFrameHandler() {
        @Override
        public Type getPayloadType(StompHeaders headers) { return PrivateMessage.class; }
        @Override
        public void handleFrame(StompHeaders headers, Object payload) {
            aliceReceived.offer((PrivateMessage) payload);
        }
    });

    StompSession bobSession = connectAs("bob");
    bobSession.send("/app/message/alice", new SendPrivateMessageRequest("Hi Alice!"));

    PrivateMessage msg = aliceReceived.poll(5, TimeUnit.SECONDS);
    assertThat(msg).isNotNull();
    assertThat(msg.getContent()).isEqualTo("Hi Alice!");

    aliceSession.disconnect();
    bobSession.disconnect();
}
```

---

## CountDownLatch Pattern (Alternative)

```java
@Test
void onConnect_serverSendsWelcomeMessage() throws Exception {
    CountDownLatch latch = new CountDownLatch(1);
    AtomicReference<WelcomeMessage> received = new AtomicReference<>();

    StompSession session = stompClient
        .connectAsync("ws://localhost:" + port + "/ws", new StompSessionHandlerAdapter() {})
        .get(5, TimeUnit.SECONDS);

    session.subscribe("/user/queue/welcome", new StompFrameHandler() {
        @Override
        public Type getPayloadType(StompHeaders headers) { return WelcomeMessage.class; }
        @Override
        public void handleFrame(StompHeaders headers, Object payload) {
            received.set((WelcomeMessage) payload);
            latch.countDown();
        }
    });

    session.send("/app/connect", new ConnectRequest());

    assertThat(latch.await(5, TimeUnit.SECONDS)).isTrue();
    assertThat(received.get().getText()).contains("Welcome");

    session.disconnect();
}
```

---

## Testing Error Frames

```java
@Test
void sendInvalidMessage_serverSendsErrorFrame() throws Exception {
    CountDownLatch errorLatch = new CountDownLatch(1);
    AtomicReference<String> errorMessage = new AtomicReference<>();

    StompSession session = stompClient
        .connectAsync("ws://localhost:" + port + "/ws", new StompSessionHandlerAdapter() {
            @Override
            public void handleException(StompSession s, StompCommand cmd,
                                         StompHeaders headers, byte[] payload, Throwable ex) {
                errorMessage.set(ex.getMessage());
                errorLatch.countDown();
            }
        })
        .get(5, TimeUnit.SECONDS);

    session.send("/app/chat", new InvalidRequest(null, null));

    assertThat(errorLatch.await(5, TimeUnit.SECONDS)).isTrue();
}
```

---

## WebSocket with Spring Security

```java
// For full integration test with auth:
// 1. Obtain a session cookie via /login before WS connect
// 2. Pass cookie in WebSocketHttpHeaders:
WebSocketHttpHeaders wsHeaders = new WebSocketHttpHeaders();
wsHeaders.add(HttpHeaders.COOKIE, "SESSION=" + sessionId);
StompSession session = stompClient
    .connectAsync(url, wsHeaders, connectHeaders, new StompSessionHandlerAdapter() {})
    .get(5, TimeUnit.SECONDS);
```

---

## What to Test Where

| Test Type | What It Covers |
|---|---|
| Unit test on `@MessageMapping` method | Handler logic, return value, exceptions — fast, no infrastructure |
| `@SpringBootTest(RANDOM_PORT)` + StompClient | Full WS handshake, STOMP routing, broadcast, @SendToUser |
| Cannot easily test | SockJS fallback reliability, broker relay (ActiveMQ/RabbitMQ) in CI |

---

## Anti-Patterns

| Anti-Pattern | Fix | Type |
|---|---|---|
| Using MockMvc for WebSocket endpoint | Use RANDOM_PORT + StompClient — MockMvc can't upgrade to WS | Principle |
| Timeout too short (1s) in `poll()` / `await()` | Use 5–10s; startup overhead is real | Principle |
| Not disconnecting sessions in `@AfterEach` | Always call `session.disconnect()` | Principle |
| Not stopping `stompClient` in `@AfterEach` | Leaks executor threads across tests | Principle |
| Assuming message order in multi-subscriber tests | Message ordering not guaranteed; use sets | Principle |
| `Thread.sleep()` for synchronization | Use BlockingQueue or Awaitility | Principle |

---

## Boot 3.x → 4.x

| Area | Boot 3.x | Boot 4.x |
|---|---|---|
| WebSocket namespace | `jakarta.websocket.*` | Same |
| `StandardWebSocketClient` | `o.s.web.socket.client.standard` | Same |
| `WebSocketStompClient` | `o.s.web.socket.messaging` | Same |
| Security WebSocket config | `AbstractSecurityWebSocketMessageBrokerConfigurer` | Deprecated; use component-based config in Security 7 |
