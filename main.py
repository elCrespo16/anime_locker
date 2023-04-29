import PySimpleGUI as sg
from controller import AnimeController, Anime
import subprocess

def make_header() -> list:
    headings = ["Name", "Next cap", "All caps", "Last day"]
    return [sg.Text(row, size=(12,1), font="Arial 16 bold", background_color="grey22", pad=((0,0),(5,0))) for row in headings]

def make_text_row(i: int, data: list) -> list:
    return ([sg.pin(
                sg.Col(
                    [[sg.Text(col,
                     size=(12,1),
                     key=(i,j),
                     font="Arial 16 bold",
                     pad=0) for j, col in enumerate(data)] + 
                     [sg.Button("+", key=("dispense", i), tooltip="Dispense this anime", pad=0),
                      sg.Button('<', key=("open_browser", i), tooltip="Open in Finder", pad=0),
                      sg.Button('X', key=('del',i), tooltip="Delete this anime", pad=0)]], 
                     key=i,
                     pad=0)
                )]
            )

def make_anime_table(animes: dict[str,Anime]) -> list[list[sg.Text]]:
    anime_list = [data.to_representation() for data in animes.values()]
    return [make_header()] + [make_text_row(i, row) for i, row in enumerate(anime_list)]

def new_anime_window(anime_controller: AnimeController) -> str:
    layout = [[sg.Text('Anime Locker', justification='c', expand_x=True, font='Arial 20 bold', text_color='white', size=50, pad=0)],
              [sg.Text("Anime name", font="Arial 16 bold"), sg.Input(key='-NAME-'), sg.Text("", font="Arial 16 bold", key="-NAME_ERRORS-")],
              [sg.Text("Path to anime", font="Arial 16 bold"), sg.In(size=(25,1), enable_events=True ,key='-FOLDER-'), sg.FolderBrowse(initial_folder="HOME")],
              [sg.Text("Caps daily", font="Arial 16 bold"), sg.Input(key='-CAPS-'), sg.Text("", font="Arial 16 bold", key="-CAPS_ERRORS-")],
              [sg.Text("Old caps", font="Arial 16 bold"), sg.Input(key='-CAPS_OLD-'), sg.Text("", font="Arial 16 bold", key="-OLD_CAPS_ERRORS-")],
              [sg.Push(), sg.Button('Create', button_color='white on grey', pad=((0, 20), 20)),
               sg.Push(), sg.Button('Back', button_color='white on grey', pad=((0, 20), 20)), sg.Push()]]

    window = sg.Window('Anime Locker', layout, font='Arial 12 bold')
    anime = None
    while True:
        event, values = window.read()
        if event == "Create":
            try:
                int(values['-CAPS-'])
            except ValueError:
                window["-CAPS_ERRORS-"].update("This must be a number")
                continue
            try:
                int(values['-CAPS_OLD-'])
            except ValueError:
                window["-OLD_CAPS_ERRORS-"].update("This must be a number")
                continue
            try:
                anime_controller.add_new_anime(values["-NAME-"], values["-FOLDER-"], int(values['-CAPS-']), values["-CAPS_OLD-"])
                anime = values["-NAME-"]
                break
            except Exception as e:
                window["-NAME_ERRORS-"].update(str(e))

        if event == sg.WIN_CLOSED or event == 'Back': # if user closes window or clicks cancel
            break

    window.close()
    return anime

def reload_anime(window, anime_controller, name, row):
    if name in anime_controller.animes:
        window[(row,1)].update(anime_controller.animes[name].old_caps + anime_controller.animes[name].next_cap)
        window[(row,2)].update(anime_controller.animes[name].old_caps + anime_controller.animes[name].caps)
        window[(row,3)].update(anime_controller.animes[name].last_day)
    else:
        window[row].update(visible=False)

def main():
    sg.theme("DarkGrey11")
    anime_controller = AnimeController()
    animes_in_view = len(anime_controller.animes.keys())

    main_layout = [  [sg.Text('Anime Locker', justification='c', expand_x=True, font='Arial 20 bold', text_color='white', size=50, pad=0)],
                [sg.Push(), sg.Text('Current animes', font="Arial 16 bold"), sg.Push()],
                [sg.Col(make_anime_table(anime_controller.animes), key="-ANIME_TABLE-")],
                [sg.Push(), sg.Button('Add new anime', button_color='white on grey', pad=((0, 20), 20)), 
                 sg.Push(), sg.Button('Reload app', key="reload", button_color='white on grey', pad=((0, 20), 20)), sg.Push()],
                [sg.Push(), sg.Button('Quit', button_color='white on grey', pad=((0, 20), 20))] ]
    
    window = sg.Window('Anime Locker', main_layout, font='Arial 12 bold', icon="./1.icns")
    while True:
        event, values = window.read()
        if event == "Add new anime":
            anime_name = new_anime_window(anime_controller=anime_controller)
            if anime_name:
                window.extend_layout(window["-ANIME_TABLE-"], [make_text_row(animes_in_view, anime_controller.animes[anime_name].to_representation())])
                msg = f"New episodes of {anime_name} are available"
                sg.popup_ok(msg, font='Arial 12 bold', auto_close=True, auto_close_duration=5)
                animes_in_view += 1
        if event == 'reload':
            anime_controller.reload()
            for i in range(animes_in_view):
                name = window[(i,0)].DisplayText
                reload_anime(window, anime_controller, name, i)
        if 'del' in event:
            anime_row = event[1]
            anime_name = window[(anime_row,0)].DisplayText
            response = sg.popup_yes_no(f"Are you sure you want to delete {anime_name}? This will delete the caps in the folder", 
                                       title=f"Delete {anime_name}")
            if response == "Yes":
                anime_controller.delete_anime(anime_name)
                reload_anime(window, anime_controller, anime_name, anime_row)
        if 'dispense' in event:
            anime_row = event[1]
            anime_name = window[(anime_row,0)].DisplayText
            response = sg.popup_yes_no(f"Are you sure you want to dispense {anime_name}? This will delete the previous caps", 
                                       title=f"Dispense {anime_name}")
            if response == "Yes":
                response = anime_controller.dispense_anime(anime_name)
                msg = "You don't have more episodes available for today bro"
                if response:
                    msg = f"New episodes of {anime_name} are available"
                    reload_anime(window, anime_controller, anime_name, anime_row)
                sg.popup_ok(msg, font='Arial 12 bold', auto_close=True, auto_close_duration=5)
        if 'open_browser' in event:
            anime_row = event[1]
            anime_name = window[(anime_row,0)].DisplayText
            subprocess.call(["open", "-R", anime_controller.animes[anime_name].path])
        if event == 'Quit': # if user closes window or clicks cancel
            break

    window.close()

if __name__ == "__main__":
    main()