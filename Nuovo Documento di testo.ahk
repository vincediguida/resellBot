; Ctrl+Shift+F prova: Add to Cart -> Checkout (finestra attiva Chrome/Edge)
^+f::
    SetTitleMatchMode, 2
    IfWinActive("Chrome") || IfWinActive("Edge")
    {
        ; Esempio generico: TAB verso il pulsante, Enter, attesa breve, poi Checkout
        Send "{Tab 8}{Enter}"
        Sleep 250
        Send "{Tab 4}{Enter}"
    }
return
