import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout, RequireAuth } from "./components/Layout";
import { AuthProvider } from "./context/AuthContext";
import { AuthPage } from "./pages/Auth";
import BuyBrowse from "./pages/BuyBrowse";
import Dashboard from "./pages/Dashboard";
import Home from "./pages/Home";
import NewRequest from "./pages/NewRequest";
import NewShipment from "./pages/NewShipment";
import PaymentResult from "./pages/PaymentResult";
import RequestDetail from "./pages/RequestDetail";
import SendBrowse from "./pages/SendBrowse";
import ShipmentDetail from "./pages/ShipmentDetail";
import TripMatches from "./pages/TripMatches";
import { NewTrip, Trips } from "./pages/Trips";
import SaathiPage from "./pages/Saathi";
import Dabbas from "./pages/Dabbas";
import ReviewQueue from "./pages/ReviewQueue";

const auth = (el: React.ReactNode) => <RequireAuth>{el}</RequireAuth>;

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<AuthPage mode="login" />} />
            <Route path="/register" element={<AuthPage mode="register" />} />
            <Route path="/buy" element={<BuyBrowse />} />
            <Route path="/buy/new" element={auth(<NewRequest />)} />
            <Route path="/buy/:id" element={<RequestDetail />} />
            <Route path="/send" element={<SendBrowse />} />
            <Route path="/send/new" element={auth(<NewShipment />)} />
            <Route path="/send/:id" element={<ShipmentDetail />} />
            <Route path="/trips" element={auth(<Trips />)} />
            <Route path="/trips/new" element={auth(<NewTrip />)} />
            <Route path="/trips/:id/matches" element={auth(<TripMatches />)} />
            <Route path="/dashboard" element={auth(<Dashboard />)} />
            <Route path="/payments/result" element={auth(<PaymentResult />)} />
            <Route path="/saathi" element={auth(<SaathiPage />)} />
            <Route path="/dabbas" element={auth(<Dabbas />)} />
            <Route path="/review" element={auth(<ReviewQueue />)} />
            <Route path="*" element={<h2>Page not found</h2>} />
          </Routes>
        </Layout>
      </AuthProvider>
    </BrowserRouter>
  );
}
