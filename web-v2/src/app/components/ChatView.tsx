import { useState } from "react";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import AdvancedTradingChart from "./AdvancedTradingChart";
import InteractiveMessage from "./InteractiveMessage";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  interactive?: boolean;
  componentType?: "table" | "card" | "code";
}

export default function ChatView() {
  const [isGenerating, setIsGenerating] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content: "Hello! I'm your AI assistant for the Market Maker project. I can help you with trading strategies, algorithm development, risk management, and more. What would you like to know?",
      timestamp: "2:30 PM"
    },
    {
      id: "2",
      role: "assistant",
      content: "strategy-performance",
      timestamp: "2:31 PM",
      interactive: true,
      componentType: "table"
    }
  ]);

  // Sample trading data with OHLCV
  const chartData = [
    { time: "09:00", open: 42100, high: 42200, low: 42050, close: 42150, volume: 25000 },
    { time: "09:30", open: 42150, high: 42320, low: 42140, close: 42280, volume: 32000 },
    { time: "10:00", open: 42280, high: 42450, low: 42260, close: 42420, volume: 28000 },
    { time: "10:30", open: 42420, high: 42430, low: 42280, close: 42350, volume: 21000 },
    { time: "11:00", open: 42350, high: 42550, low: 42340, close: 42500, volume: 35000 },
    { time: "11:30", open: 42500, high: 42680, low: 42490, close: 42650, volume: 40000 },
    { time: "12:00", open: 42650, high: 42670, low: 42520, close: 42580, volume: 26000 },
    { time: "12:30", open: 42580, high: 42750, low: 42570, close: 42720, volume: 31000 },
    { time: "13:00", open: 42720, high: 42920, low: 42710, close: 42890, volume: 38000 },
    { time: "13:30", open: 42890, high: 42980, low: 42870, close: 42950, volume: 29000 },
    { time: "14:00", open: 42950, high: 43150, low: 42940, close: 43100, volume: 42000 },
    { time: "14:30", open: 43100, high: 43120, low: 43010, close: 43050, volume: 27000 },
    { time: "15:00", open: 43050, high: 43250, low: 43040, close: 43200, volume: 36000 }
  ];

  const tradeMarkers = [
    { time: "10:00", price: 42420, type: "long" as const, label: "Long Entry" },
    { time: "11:30", price: 42650, type: "short" as const, label: "Short Entry" },
    { time: "14:00", price: 43100, type: "long" as const, label: "Long Entry" }
  ];

  const handleSendMessage = (content: string) => {
    const newMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, newMessage]);
    setIsGenerating(true);

    setTimeout(() => {
      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "I understand your question. As an AI assistant specialized in market making and algorithmic trading, I'm here to help you develop robust trading strategies.\n\nFor market making specifically, here are some key considerations:\n\n1. **Spread Management**: Maintain competitive bid-ask spreads while ensuring profitability\n2. **Inventory Risk**: Monitor and manage position sizes to avoid overexposure\n3. **Latency Optimization**: Minimize execution delays for better price capture\n4. **Market Data Analysis**: Use real-time data to adjust strategies dynamically\n\nHere's your current portfolio performance:",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      const interactiveResponse: Message = {
        id: (Date.now() + 2).toString(),
        role: "assistant",
        content: "portfolio-stats",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        interactive: true,
        componentType: "card"
      };
      setMessages(prev => [...prev, aiResponse, interactiveResponse]);
      setIsGenerating(false);
    }, 1500);
  };

  const handleStopGenerating = () => {
    setIsGenerating(false);
  };

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto p-6 space-y-6">
          {/* Trading Chart */}
          <AdvancedTradingChart data={chartData} markers={tradeMarkers} />

          {/* Chat Messages */}
          <div className="space-y-4">
            {messages.map((message) => (
              message.interactive ? (
                <InteractiveMessage
                  key={message.id}
                  type={message.componentType}
                  content={message.content}
                  timestamp={message.timestamp}
                />
              ) : (
                <div key={message.id} className="bg-card border border-border rounded-lg overflow-hidden">
                  <ChatMessage
                    role={message.role}
                    content={message.content}
                    timestamp={message.timestamp}
                  />
                </div>
              )
            ))}

            {isGenerating && (
              <div className="px-6 py-6 bg-muted/30">
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
                    <div className="w-4 h-4 border-2 border-accent-foreground border-t-transparent rounded-full animate-spin" />
                  </div>
                  <div className="flex-1">
                    <span className="text-muted-foreground">Thinking...</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Input */}
      <ChatInput
        onSend={handleSendMessage}
        isGenerating={isGenerating}
        onStop={handleStopGenerating}
      />
    </div>
  );
}
