import { useState } from "react";

function App() {
  const [count, setCount] = useState(0);

  return (
    <main className="page">
      <section className="card">
        <p className="eyebrow">FSE100 Master Project - Bubble</p>
        <h1>React + TypeScript</h1>
        <p className="description">
          React Startup
        </p>
      </section>
    </main>
  );
}

export default App;
