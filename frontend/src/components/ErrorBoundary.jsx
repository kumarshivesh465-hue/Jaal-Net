import React from "react";
import { AlertOctagon, RotateCcw } from "lucide-react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("UI Uncaught Error Boundary caught:", error, errorInfo);
  }

  componentDidUpdate(prevProps) {
    if (this.props.resetKey !== prevProps.resetKey && this.state.hasError) {
      this.setState({ hasError: false, error: null });
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) this.props.onReset();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="liquid-glass p-8 sm:p-12 text-center rounded-3xl border border-red-200/80 my-8 shadow-xl max-w-2xl mx-auto">
          <div className="w-14 h-14 rounded-2xl bg-red-100 text-[#FF0055] grid place-items-center mx-auto mb-4 shadow-sm">
            <AlertOctagon size={28} />
          </div>
          <h2 className="text-xl font-bold font-sans text-slate-900 mb-2">
            View Render Recovery
          </h2>
          <p className="text-xs text-slate-600 mb-6 font-mono2 bg-slate-100/80 p-3 rounded-xl border border-slate-200/60 overflow-x-auto text-left">
            {this.state.error?.message || "An unexpected view error occurred while rendering the graph."}
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={this.handleReset}
              className="btn-sift-pink text-xs !py-2.5 !px-5 flex items-center gap-2 cursor-pointer shadow-md"
            >
              <RotateCcw size={14} />
              <span>Reset & Reload View</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
