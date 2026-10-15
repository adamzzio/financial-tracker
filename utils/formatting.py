BULAN_SINGKAT = [
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
]


def rupiah(nilai: float) -> str:
    """Format angka ke Rupiah, contoh: Rp 12.500.000"""
    tanda = "-" if nilai < 0 else ""
    angka = f"{abs(int(round(nilai))):,}".replace(",", ".")
    return f"{tanda}Rp {angka}"