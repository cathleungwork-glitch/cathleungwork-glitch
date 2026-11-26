"""US medical names the screen is allowed to hold.

Groups are a preference, not a story. `ai_core` is a business built on
computational discovery, clinical AI, or diagnostic machine learning.
`ai_applied` is a device, imaging, robotics, or data platform that ships
those methods inside a medical product. `medical` is the rest of the
liquid medical universe. Insurers and drug distributors are left out.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Name:
    ticker: str
    company: str
    group: str  # ai_core, ai_applied, medical


AI_RANK = {"ai_core": 2, "ai_applied": 1, "medical": 0}

UNIVERSE: tuple[Name, ...] = (
    # Computational discovery, clinical AI, diagnostic ML.
    Name("TEM", "Tempus AI", "ai_core"),
    Name("RXRX", "Recursion Pharmaceuticals", "ai_core"),
    Name("SDGR", "Schrödinger", "ai_core"),
    Name("CERT", "Certara", "ai_core"),
    Name("ABCL", "AbCellera", "ai_core"),
    Name("RLAY", "Relay Therapeutics", "ai_core"),
    Name("VEEV", "Veeva Systems", "ai_core"),
    Name("DOCS", "Doximity", "ai_core"),
    Name("HCAT", "Health Catalyst", "ai_core"),
    Name("PHR", "Phreesia", "ai_core"),
    Name("IRTC", "iRhythm Technologies", "ai_core"),
    Name("NTRA", "Natera", "ai_core"),
    Name("GH", "Guardant Health", "ai_core"),
    Name("EXAS", "Exact Sciences", "ai_core"),
    Name("VCYT", "Veracyte", "ai_core"),
    Name("MYGN", "Myriad Genetics", "ai_core"),
    Name("CDNA", "CareDx", "ai_core"),
    Name("NEO", "NeoGenomics", "ai_core"),
    Name("ILMN", "Illumina", "ai_core"),
    Name("TXG", "10x Genomics", "ai_core"),
    Name("PACB", "Pacific Biosciences", "ai_core"),
    Name("TWST", "Twist Bioscience", "ai_core"),
    Name("BFLY", "Butterfly Network", "ai_core"),
    # Imaging, robotics, algorithmic devices, clinical data platforms.
    Name("GEHC", "GE HealthCare", "ai_applied"),
    Name("ISRG", "Intuitive Surgical", "ai_applied"),
    Name("SYK", "Stryker", "ai_applied"),
    Name("MDT", "Medtronic", "ai_applied"),
    Name("HOLX", "Hologic", "ai_applied"),
    Name("DXCM", "Dexcom", "ai_applied"),
    Name("PODD", "Insulet", "ai_applied"),
    Name("IQV", "IQVIA", "ai_applied"),
    Name("IDXX", "IDEXX Laboratories", "ai_applied"),
    Name("DGX", "Quest Diagnostics", "ai_applied"),
    Name("LH", "Labcorp", "ai_applied"),
    # Tools, devices, and therapeutics. Eligible, not preferred.
    Name("TMO", "Thermo Fisher Scientific", "medical"),
    Name("DHR", "Danaher", "medical"),
    Name("A", "Agilent Technologies", "medical"),
    Name("RVTY", "Revvity", "medical"),
    Name("WAT", "Waters", "medical"),
    Name("MTD", "Mettler-Toledo", "medical"),
    Name("BRKR", "Bruker", "medical"),
    Name("TECH", "Bio-Techne", "medical"),
    Name("BIO", "Bio-Rad Laboratories", "medical"),
    Name("QGEN", "Qiagen", "medical"),
    Name("WST", "West Pharmaceutical Services", "medical"),
    Name("RGEN", "Repligen", "medical"),
    Name("AVTR", "Avantor", "medical"),
    Name("CRL", "Charles River Laboratories", "medical"),
    Name("ICLR", "ICON", "medical"),
    Name("MEDP", "Medpace", "medical"),
    Name("BSX", "Boston Scientific", "medical"),
    Name("EW", "Edwards Lifesciences", "medical"),
    Name("ABT", "Abbott Laboratories", "medical"),
    Name("BDX", "Becton Dickinson", "medical"),
    Name("BAX", "Baxter International", "medical"),
    Name("STE", "STERIS", "medical"),
    Name("RMD", "ResMed", "medical"),
    Name("ZBH", "Zimmer Biomet", "medical"),
    Name("COO", "The Cooper Companies", "medical"),
    Name("ALGN", "Align Technology", "medical"),
    Name("PEN", "Penumbra", "medical"),
    Name("INSP", "Inspire Medical Systems", "medical"),
    Name("NVCR", "Novocure", "medical"),
    Name("GKOS", "Glaukos", "medical"),
    Name("TFX", "Teleflex", "medical"),
    Name("SOLV", "Solventum", "medical"),
    Name("ZTS", "Zoetis", "medical"),
    Name("LLY", "Eli Lilly", "medical"),
    Name("NVO", "Novo Nordisk", "medical"),
    Name("AMGN", "Amgen", "medical"),
    Name("GILD", "Gilead Sciences", "medical"),
    Name("REGN", "Regeneron Pharmaceuticals", "medical"),
    Name("VRTX", "Vertex Pharmaceuticals", "medical"),
    Name("BIIB", "Biogen", "medical"),
    Name("MRK", "Merck", "medical"),
    Name("ABBV", "AbbVie", "medical"),
    Name("PFE", "Pfizer", "medical"),
    Name("BMY", "Bristol-Myers Squibb", "medical"),
    Name("JNJ", "Johnson & Johnson", "medical"),
    Name("AZN", "AstraZeneca", "medical"),
    Name("NVS", "Novartis", "medical"),
    Name("SNY", "Sanofi", "medical"),
    Name("GSK", "GSK", "medical"),
    Name("ARGX", "argenx", "medical"),
    Name("ALNY", "Alnylam Pharmaceuticals", "medical"),
    Name("BMRN", "BioMarin Pharmaceutical", "medical"),
    Name("INCY", "Incyte", "medical"),
    Name("IONS", "Ionis Pharmaceuticals", "medical"),
    Name("UTHR", "United Therapeutics", "medical"),
    Name("NBIX", "Neurocrine Biosciences", "medical"),
    Name("HALO", "Halozyme Therapeutics", "medical"),
    Name("JAZZ", "Jazz Pharmaceuticals", "medical"),
)

BENCHMARKS = ("SPY", "QQQ", "XLV", "XBI", "IBB", "IHI", "ARKG", "BOXX", "SGD=X")

# Cash ballast. Counts toward the contest position ratio. Not a medical holding.
BALLAST = "BOXX"
