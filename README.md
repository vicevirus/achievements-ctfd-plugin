# achievements-ctfd-plugin
This plugin is hardcoded on some parts. Here are the details:

- You might need to edit directly  __init__.py inside the plugin to add achievements.
- It is also based on the category name, which by default CTFd is using user-entered text instead of selection.
- Thus, you may need to set the plugin to match the category name, or change the textbox to be a selectbox directly in CTFD\themes\admin\templates\create.html.
- I tried overriding the create.html inside the plugin, but it didn’t work.
- It’s up to you to make this plugin better, do a pull request if you're keen.
