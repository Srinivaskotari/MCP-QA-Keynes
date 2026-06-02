import React, { useEffect, useState } from "react";
import axios from "axios";

function App() {

  const [stats, setStats] = useState(null);

  const API = "https://mcp-qa.keynes-ai.com/api";

  useEffect(() => {

    const loadStats = async () => {

      try {

        const response = await axios.get(
          `${API}/query-stats`
        );

        console.log(response.data);

        setStats(response.data);

      } catch (err) {

        console.error(
          "API ERROR:",
          err
        );

      }

    };

    loadStats();

  }, []);

  return (

    <div
      style={{
        padding: "40px",
        fontFamily: "Arial",
        backgroundColor: "#f5f5f5",
        minHeight: "100vh"
      }}
    >

      <h1>
        Keynes QA MCP Dashboard
      </h1>

      <div
        style={{
          marginTop: "30px",
          backgroundColor: "white",
          padding: "20px",
          borderRadius: "10px",
          boxShadow:
            "0px 2px 8px rgba(0,0,0,0.1)"
        }}
      >

        <h2>
          Query Statistics
        </h2>

        {

          stats ? (

            <div>

              <p>
                <strong>Total Queries:</strong>
                {" "}
                {stats.total_queries}
              </p>

              <p>
                <strong>Completed:</strong>
                {" "}
                {stats.completed}
              </p>

              <p>
                <strong>Failed:</strong>
                {" "}
                {stats.failed}
              </p>

              <p>
                <strong>Average Latency:</strong>
                {" "}
                {stats.average_latency_seconds}s
              </p>

            </div>

          ) : (

            <p>
              Loading dashboard...
            </p>

          )

        }

      </div>

    </div>

  );

}

export default App;
