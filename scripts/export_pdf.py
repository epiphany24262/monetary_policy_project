"""Standalone Word COM PDF export with robust error handling."""
import sys
import time
from pathlib import Path

def export_pdf():
    docx = Path(r'D:\PyCharm\Quant\monetary_policy_project\paper\课程论文_提交版.docx').resolve()
    pdf = Path(r'D:\PyCharm\Quant\monetary_policy_project\paper\课程论文_提交版.pdf').resolve()
    
    if not docx.exists():
        print(f"ERROR: DOCX not found: {docx}")
        sys.exit(1)
    
    import win32com.client
    import pythoncom
    
    pythoncom.CoInitialize()
    word = None
    try:
        print("Starting Word COM...", flush=True)
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0  # wdAlertsNone
        
        print(f"Opening: {docx}", flush=True)
        doc = word.Documents.Open(
            str(docx),
            ConfirmConversions=False,
            ReadOnly=False,
            AddToRecentFiles=False,
        )
        
        print("Saving...", flush=True)
        doc.Save()
        
        print(f"Exporting PDF: {pdf}", flush=True)
        doc.ExportAsFixedFormat(
            str(pdf),
            ExportFormat=17,  # wdExportFormatPDF
            OptimizeFor=0,    # wdExportOptimizeForPrint
        )
        
        print("Closing document...", flush=True)
        doc.Close(False)
        
        print("Quitting Word...", flush=True)
        word.Quit()
        word = None
        
        if pdf.exists():
            print(f"SUCCESS: PDF exported, size={pdf.stat().st_size}", flush=True)
        else:
            print("ERROR: PDF file not created", flush=True)
            sys.exit(1)
            
    except Exception as exc:
        print(f"ERROR: {exc}", flush=True)
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        sys.exit(1)
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    export_pdf()
