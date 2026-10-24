"""IATA airport code -> (city, ISO country). Extend as needed."""

AIRPORTS: dict[str, tuple[str, str]] = {
    # India
    "DEL": ("Delhi", "IN"), "BOM": ("Mumbai", "IN"), "BLR": ("Bengaluru", "IN"), "MAA": ("Chennai", "IN"),
    "HYD": ("Hyderabad", "IN"), "CCU": ("Kolkata", "IN"), "COK": ("Kochi", "IN"), "AMD": ("Ahmedabad", "IN"),
    "PNQ": ("Pune", "IN"), "GOI": ("Goa", "IN"), "GOX": ("Goa", "IN"), "TRV": ("Thiruvananthapuram", "IN"),
    "CCJ": ("Kozhikode", "IN"), "CNN": ("Kannur", "IN"), "IXE": ("Mangaluru", "IN"), "LKO": ("Lucknow", "IN"),
    "JAI": ("Jaipur", "IN"), "ATQ": ("Amritsar", "IN"), "IXC": ("Chandigarh", "IN"), "TRZ": ("Tiruchirappalli", "IN"),
    "CJB": ("Coimbatore", "IN"), "VNS": ("Varanasi", "IN"), "NAG": ("Nagpur", "IN"), "BBI": ("Bhubaneswar", "IN"),
    "GAU": ("Guwahati", "IN"), "IDR": ("Indore", "IN"), "PAT": ("Patna", "IN"), "SXR": ("Srinagar", "IN"),
    "VTZ": ("Visakhapatnam", "IN"), "IXM": ("Madurai", "IN"),
    # Middle East
    "DXB": ("Dubai", "AE"), "DWC": ("Dubai", "AE"), "AUH": ("Abu Dhabi", "AE"), "SHJ": ("Sharjah", "AE"),
    "DOH": ("Doha", "QA"), "RUH": ("Riyadh", "SA"), "JED": ("Jeddah", "SA"), "DMM": ("Dammam", "SA"),
    "KWI": ("Kuwait City", "KW"), "MCT": ("Muscat", "OM"), "BAH": ("Manama", "BH"),
    # Asia
    "SIN": ("Singapore", "SG"), "KUL": ("Kuala Lumpur", "MY"), "BKK": ("Bangkok", "TH"), "DMK": ("Bangkok", "TH"),
    "HKG": ("Hong Kong", "HK"), "NRT": ("Tokyo", "JP"), "HND": ("Tokyo", "JP"), "KIX": ("Osaka", "JP"),
    "PEK": ("Beijing", "CN"), "PVG": ("Shanghai", "CN"), "CMB": ("Colombo", "LK"), "KTM": ("Kathmandu", "NP"),
    # Europe
    "LHR": ("London", "GB"), "LGW": ("London", "GB"), "STN": ("London", "GB"), "MAN": ("Manchester", "GB"),
    "BHX": ("Birmingham", "GB"), "EDI": ("Edinburgh", "GB"), "FRA": ("Frankfurt", "DE"), "MUC": ("Munich", "DE"),
    "BER": ("Berlin", "DE"), "CDG": ("Paris", "FR"), "AMS": ("Amsterdam", "NL"), "FCO": ("Rome", "IT"),
    "MXP": ("Milan", "IT"), "MAD": ("Madrid", "ES"), "BCN": ("Barcelona", "ES"), "DUB": ("Dublin", "IE"),
    "ZRH": ("Zurich", "CH"), "GVA": ("Geneva", "CH"),
    # North America
    "JFK": ("New York", "US"), "EWR": ("Newark", "US"), "SFO": ("San Francisco", "US"), "LAX": ("Los Angeles", "US"),
    "ORD": ("Chicago", "US"), "IAD": ("Washington", "US"), "SEA": ("Seattle", "US"), "BOS": ("Boston", "US"),
    "ATL": ("Atlanta", "US"), "DFW": ("Dallas", "US"), "IAH": ("Houston", "US"), "SJC": ("San Jose", "US"),
    "YYZ": ("Toronto", "CA"), "YVR": ("Vancouver", "CA"), "YUL": ("Montreal", "CA"), "YYC": ("Calgary", "CA"),
    # Oceania
    "SYD": ("Sydney", "AU"), "MEL": ("Melbourne", "AU"), "BNE": ("Brisbane", "AU"), "PER": ("Perth", "AU"),
    "ADL": ("Adelaide", "AU"), "AKL": ("Auckland", "NZ"),
}

# City names that commonly appear on boarding passes instead of IATA codes.
CITY_ALIASES: dict[str, str] = {
    "NEW DELHI": "DEL", "DELHI": "DEL", "MUMBAI": "BOM", "BOMBAY": "BOM", "BENGALURU": "BLR", "BANGALORE": "BLR",
    "CHENNAI": "MAA", "MADRAS": "MAA", "HYDERABAD": "HYD", "KOLKATA": "CCU", "KOCHI": "COK", "COCHIN": "COK",
    "AHMEDABAD": "AMD", "PUNE": "PNQ", "DUBAI": "DXB", "ABU DHABI": "AUH", "SHARJAH": "SHJ", "DOHA": "DOH",
    "RIYADH": "RUH", "JEDDAH": "JED", "MUSCAT": "MCT", "SINGAPORE": "SIN", "KUALA LUMPUR": "KUL",
    "BANGKOK": "BKK", "HONG KONG": "HKG", "LONDON": "LHR", "FRANKFURT": "FRA", "PARIS": "CDG",
    "AMSTERDAM": "AMS", "NEW YORK": "JFK", "SAN FRANCISCO": "SFO", "CHICAGO": "ORD", "TORONTO": "YYZ",
    "SYDNEY": "SYD", "MELBOURNE": "MEL",
}
